import os
import time
import json
import argparse
import logging
import sys
import plotly.graph_objects as go
from dataclasses import dataclass


def setup_logs(level):
    """send paramiko logs to a logfile,
    if they're not already going somewhere"""

    frm = "%(levelname)-.3s [%(asctime)s.%(msecs)03d]"
    frm += " %(name)s: %(message)s"
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(frm, "%Y%m%d-%H:%M:%S"))
    logging.basicConfig(level=level, handlers=[handler])


logger = logging.getLogger(__name__)
HOVER_TEMPLATE = "code: {}</br>comments: {}</br>blanks: {}</br>"

colors_raw = json.load(open(os.path.dirname(__file__) + "/colors.json", "r"))
# from: https://github.com/ozh/github-colors/blob/master/colors.json
LANGCOLOR = {k.lower(): v["color"] for k, v in colors_raw.items()}


@dataclass
class Sector:
    id: str
    label: str

    parent_id: str
    lang_type: str

    code: int = 0
    blanks: int = 0
    comments: int = 0
    inaccurate: bool = False


def draw(sectors, to_html):
    ids = []
    labels = []
    parents = []
    values = []
    hover_texts = []
    colors = []
    for s in sectors:
        logger.debug("sector: {}".format(s))
        ids.append(s.id)
        labels.append(s.label)
        parents.append(s.parent_id)
        values.append(s.code + s.comments + s.blanks)
        hover_texts.append(HOVER_TEMPLATE.format(s.code, s.comments, s.blanks))
        lang = s.lang_type
        colors.append(LANGCOLOR.get(lang.lower()))

    logger.info("got {} sectors...".format(len(ids)))

    logger.debug("ids: {}".format(ids))
    logger.debug("labels: {}".format(labels))
    logger.debug("parents: {}".format(parents))
    logger.debug("values: {}".format(values))

    fig = go.Figure(
        go.Sunburst(
            ids=ids,
            labels=labels,
            parents=parents,
            values=values,
            branchvalues="total",
            hovertext=hover_texts,
            marker=dict(colors=colors, autocolorscale=True),
        )
    )
    fig.update_layout(
        margin=dict(t=30, l=0, r=0, b=0), title="tokei-pie source code chart"
    )

    if to_html:
        fig.write_html(to_html)
    else:
        fig.show()


def build_file_tree(reports):
    # {location: direct sub files}
    tree = {}
    for report in reports:
        full_filename = report["name"]
        pathes = full_filename.split(os.sep)
        last = pathes[0]
        for path in pathes[1:]:
            current = last + os.sep + path
            tree.setdefault(last, set()).add(current)
            last = current
    return tree


def convert2sectors(dirs, reports, language):
    flat_dirs = dirs.keys()
    logger.debug(f"flat_dirs: {flat_dirs}")
    logger.debug(f"reports: {reports}")
    logger.debug(f"dirs: {dirs}")

    def dir2sector(dirname, dirs, reports, sectors, language):
        logger.debug(f"dir2sector({dirname}, {dirs} ...)")
        subdirs = dirs[dirname]

        blanks = code = comments = 0
        for item in subdirs:
            is_file = item not in flat_dirs
            if is_file:
                stats = reports[item]
                base_dirs = item.split(os.sep)
                base_dirs[0] = language
                parent_id = os.sep.join(base_dirs[:-1])
                filename = base_dirs[-1]
                myid = os.sep.join(base_dirs)
                sectors.append(
                    Sector(
                        id=item,
                        label=filename,
                        parent_id=parent_id,
                        code=stats.get("code"),
                        blanks=stats.get("blanks"),
                        comments=stats.get("comments"),
                        lang_type=language,
                    )
                )

                blanks += stats["blanks"]
                code += stats["code"]
                comments += stats["comments"]
            else:
                _blanks, _code, _comments = dir2sector(
                    item, dirs, reports, sectors, language
                )
                blanks += _blanks
                code += _code
                comments += _comments

        if dirname == ".":
            return 0, 0, 0
        base_dirs = dirname.split(os.sep)
        filename = base_dirs[-1]
        base_dirs[0] = language
        parent_id = os.sep.join(base_dirs[:-1])
        myid = os.sep.join(base_dirs)
        sectors.append(
            Sector(
                id=myid,
                label=filename,
                parent_id=parent_id,
                code=code,
                blanks=blanks,
                comments=comments,
                lang_type=language,
            )
        )
        return blanks, code, comments

    sectors = []
    head = list(dirs.keys())[0]
    dir2sector(head, dirs, reports, sectors, language)
    return sectors


def read_reports(reports, parent_id):
    tree = build_file_tree(reports)
    logger.debug(f"get tree for {parent_id}: {tree}")
    dict_reports = {i["name"]: i["stats"] for i in reports}
    sectors = convert2sectors(tree, dict_reports, parent_id)
    return sectors


def read_root(data):
    sectors = []
    for key, value in data.items():
        if key == "Total":
            continue
        sector = Sector(
            id=key,
            label=key,
            parent_id="",
            code=value.get("code"),
            blanks=value.get("blanks"),
            comments=value.get("comments"),
            inaccurate=value.get("inaccurate"),
            lang_type=key,
        )
        sectors.append(sector)
        reports = value["reports"]
        sectors.extend(read_reports(reports, key))
    return sectors


def common_prefix(prefixes, strings):
    passed = current_prefix = ""
    for prefix in prefixes:
        current_prefix = current_prefix + prefix + os.sep
        if any(not s.startswith(current_prefix) for s in strings):
            return passed
        passed = current_prefix


def pre_parse_data(data):
    reports = []
    for value in data.values():
        reports.extend(t["name"] for t in value.get("reports"))

    one = reports[0]
    pathes = one.split(os.sep)
    common_prefix_str = common_prefix(pathes, reports)

    prefix_len = len(common_prefix_str)
    for value in data.values():
        for report in value.get("reports"):
            report["name"] = "." + os.sep + report["name"][prefix_len:]

    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="count", default=0)
    parser.add_argument(
        "-o",
        "--output-html",
        metavar="filename",
        help="write chart to html instead of open your browser to display",
    )
    args = parser.parse_args()
    if args.verbose == 0:
        pass
    elif args.verbose == 1:
        setup_logs(logging.INFO)
    elif args.verbose == 2:
        setup_logs(logging.DEBUG)

    start = time.time()
    try:
        data = json.load(sys.stdin)
    except json.decoder.JSONDecodeError:
        print(
            "Stdin is not json, please pass tokei's json output to tokei-pie, like this: tokei -o json | tokei-pie",
            file=sys.stderr,
        )
        sys.exit(128)

    data = pre_parse_data(data)
    load_time = time.time()
    logger.info("load json file done, took {:.2f}s".format(load_time - start))
    sectors = read_root(data)
    parse_file_time = time.time()
    logger.info(
        "parse tokei data done, took {:.2f}s".format(parse_file_time - load_time)
    )
    draw(sectors, args.output_html)
    draw_time = time.time()
    logger.info(
        "draw sunburst chart done, took {:.2f}s".format(draw_time - parse_file_time)
    )


if __name__ == "__main__":
    main()
