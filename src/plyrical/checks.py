from os.path import exists


def check_tags_exist(ctx, file, meta):

    artist = meta.get("artist", meta.get("albumartist", None))
    album = meta.get("album", None)
    title = meta.get("title", None)
    if artist is None or album is None or title is None:
        ctx.obj["logger"].warning(
            f'file="{file}" artist={artist} album={album} title={title}'
            f' msg="Critical tag missing. Skipping file"'
        )
        return False
    else:
        return True


def lyric_tag_exists(ctx, file, meta):

    artist = meta.get("artist", meta.get("albumartist", None))
    album = meta.get("album", None)
    title = meta.get("title", None)
    if meta[ctx.obj["read_tag"]]:
        ctx.obj["logger"].info(
            f'file="{file}" artist={artist} album={album} '
            f'title={title} tag_name={ctx.obj["read_tag"]} '
            f'msg="Lyrics already exist in tag. Skipping file"'
        )
        return True
    else:
        return False


def lrc_file_exists(ctx, file):

    base_name = str(file).rsplit(".", 1)[0]
    lrc_file = base_name + ".lrc"
    if exists(lrc_file):
        return True, lrc_file
    else:
        return False, lrc_file
