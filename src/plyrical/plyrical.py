import click_config_file
import enlighten
import os
import rich_click as click

from mutagen import File
from providers.kugou import Kugou
from providers.musixmatch import Musixmatch
from plyrical.checks import check_tags_exist, lrc_file_exists
from plyrical.scanner import scan_dir
from plyrical.utils import _init_logger


main_provider = click_config_file.configobj_provider(section="plyrical")


@click.command("cli", context_settings={"show_default": True})
@click.option(
    "--log-level",
    "-l",
    type=click.Choice(["INFO", "DEBUG"], case_sensitive=True),
    default="INFO",
    show_default=True,
)
@click.option(
    "--write-tag",
    "-wt",
    default="LYRICS",
    help="The tag to write lyrics to",
    show_default=True,
)
@click.option(
    "--read-tag",
    "-rt",
    default="LYRICS",
    help="The tag to read lyrics from to determine if they have lyrics",
    show_default=True,
)
@click.option(
    "--artist-tag",
    "-at",
    default="ARTIST",  # this should probably be ALBUMARTIST
    help="The tag to read the artist from to pass to the provider",
    show_default=True,
)
@click.option(
    "--extensions",
    "-e",
    type=click.Choice(["flac", "mp3"], case_sensitive=True),
    multiple=True,
    default=["flac", "mp3"],
    help="The type of music files to scan for. "
    "Supported types are currently flac and mp3",
    show_default=True,
)
@click.option(
    "--directory",
    "-d",
    required=True,
    help="The directory to (recursively) scan for music files",
)
@click.option(
    "--overwrite-lrc/--no-overwrite-lrc",
    "-ol/-nol",
    default=False,
    help="Whether or not to overwrite existing lrc files",
    show_default=True,
)
@click.option(
    "--overwrite-tag/--no-overwrite-tag",
    "-ot/-not",
    default=False,
    help="Whether or not to overwrite existing tag",
    show_default=True,
)
@click.option(
    "--tags/--no-tags",
    "-t/-nt",
    default=True,
    help="Write lyrics to defined write tag (default LYRICS)",
    show_default=True,
)
@click.option(
    "--lrc/--no-lrc",
    "-l/-nl",
    default=True,
    help="Write lyrics to .lrc file (same name as file)",
    show_default=True,
)
@click.option(
    "--api-url",
    "-a",
    default="https://apic-desktop.musixmatch.com/ws/1.1/",
    help="Use to override default URL for the API",
)
@click.option(
    "--token-sleep-seconds",
    "-tss",
    default=10,
    help="If we encounter a captcha rate limit, how many seconds to sleep "
    "before trying to get another user_token",
)
@click.version_option()
@click_config_file.configuration_option(
    provider=main_provider,
    default=os.path.expanduser("~") + "/.plyricalrc",
    show_default=True,
    implicit=False,
)
@click.pass_context
def cli(
    ctx,
    log_level,
    write_tag,
    read_tag,
    artist_tag,
    extensions,
    directory,
    overwrite_lrc,
    overwrite_tag,
    tags,
    lrc,
    api_url,
    token_sleep_seconds,
):

    # put params in obj
    ctx.obj = ctx.params
    # init logger
    ctx.obj["logger"] = _init_logger(log_level)

    mxm = Musixmatch(ctx, api_url=api_url, token_sleep_seconds=token_sleep_seconds)
    kugou = Kugou(ctx)
    # gather files
    files = scan_dir(directory=ctx.obj["directory"], extensions=ctx.obj["extensions"])
    # progress bar stuff
    num_files = len(files)
    manager = enlighten.get_manager()
    pbar = manager.counter(total=num_files, desc="files:", unit="files", color="green")
    status_format = "file:{file}{fill}artist:{artist} album:{album} title:{title}"
    status_bar = manager.status_bar(
        status_format=status_format,
        color="bold_slategray",
        file="",
        artist="",
        album="",
        title="",
        position=1,
    )
    for file in files:
        # read tags
        meta = File(file)
        length = meta.info.length * 1000  # in milliseconds
        # check if we have all the required tags (artist, album, title)
        if not check_tags_exist(ctx=ctx, file=file, meta=meta):
            ctx.obj["logger"].warning(f'file="{file}" status="couldnt find tag"')
            pbar.update()
            continue
        # can update status bar now that we know we have valid tags to use
        status_bar.update(
            file=file, artist=meta["artist"], album=meta["album"], title=meta["title"]
        )

        # figure out all the things that exist or don't
        lrc_exists, lrc_file = lrc_file_exists(ctx, file)
        tag_exists = True if meta.get(ctx.obj["read_tag"]) else False

        # we already have a tag and file and we
        # are not overwriting either so bail on this track
        if (
            lrc_exists
            and not ctx.obj["overwrite_lrc"]
            and tag_exists
            and not ctx.obj["overwrite_tag"]
        ):
            ctx.obj["logger"].info(
                f'file="{file}" lrc_file="{lrc_file}" status="both exist" msg=skipping'
            )
            pbar.update()
            continue

        lyrics = mxm.get_lyrics_by_metadata(
            artist_name=meta[ctx.obj["artist_tag"]],
            track_name=meta["title"],
            album_name=meta["album"],
        )
        if not lyrics:
            lyrics = kugou.get_lyric_by_metadata(
                artist=meta[ctx.obj["artist_tag"]], title=meta["title"], duration=length
            )

        # nothing to write so bail on this track
        if not lyrics:
            ctx.obj["logger"].info(
                f'file="{file}" artist={meta["artist"]} album={meta["album"]} '
                f'title={meta["title"]} msg="No lyrics found! Skipping"'
            )
            pbar.update()
            continue

        # sometimes we receive a byte-like object instead of a str
        lyrics = str(lyrics)

        # we are configured to write tags and they don't exist on the file
        if ctx.obj["tags"] and not tag_exists:
            ctx.obj["logger"].info(
                f'file="{file}" artist={meta["artist"]} album={meta["album"]} '
                f'title={meta["title"]} status=writing tag={ctx.obj["write_tag"]}'
            )
            meta[ctx.obj["write_tag"]] = lyrics
            meta.save()
        # we are configured to write tags, the tag exists, and we will overwrite
        elif ctx.obj["tags"] and tag_exists and ctx.obj["overwrite_tag"]:
            ctx.obj["logger"].info(
                f'file="{file}" artist={meta["artist"]} album={meta["album"]} '
                f'title={meta["title"]} status=writing tag={ctx.obj["write_tag"]}'
            )
            meta[ctx.obj["write_tag"]] = lyrics
            meta.save()
        # tag exists and we are not overwriting, so just log
        elif ctx.obj["tags"] and tag_exists and not ctx.obj["overwrite_tag"]:
            ctx.obj["logger"].info(
                f'file="{file}" item=tag status="exists" msg=skipping'
            )
        # we aren't supposed to write tags at all
        elif not ctx.obj["tags"]:
            pass

        # we are configured to write an lrc file and it doesn't exist yet
        if ctx.obj["lrc"] and not lrc_exists:
            ctx.obj["logger"].info(
                f'file="{lrc_file}" artist={meta["artist"]} album={meta["album"]} '
                f'title={meta["title"]} status=writing_lrc'
            )
            with open(lrc_file, "w") as output_file:
                output_file.write(lyrics)
        # we are configured to write an lrc file and we want to overwrite
        elif ctx.obj["lrc"] and ctx.obj["overwrite_lrc"]:
            ctx.obj["logger"].info(
                f'file="{lrc_file}" artist={meta["artist"]} album={meta["album"]} '
                f'title={meta["title"]} status=writing_lrc'
            )
            with open(lrc_file, "w") as output_file:
                output_file.write(lyrics)
        # lrc file already exists and we are not going to overwrite
        elif ctx.obj["lrc"] and lrc_exists and not ctx.obj["overwrite_lrc"]:
            ctx.obj["logger"].info(
                f'file="{lrc_file}" item=lrc status="exists" msg=skipping'
            )
        # we aren't supposed to write an lrc file at all
        elif not ctx.obj["lrc"]:
            pass

        pbar.update()
