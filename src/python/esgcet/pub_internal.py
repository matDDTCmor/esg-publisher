from esgcet.args import PublisherArgs
import os
import sys
import esgcet.logger as logger

log = logger.ESGPubLogger()
publog = log.return_logger("Publisher-Main")

from pathlib import Path
from esgcet.generic_netcdf import GenericPublisher
from esgcet.generic_pub import BasePublisher
from esgcet.cmip6 import cmip6
from esgcet.input4mips import input4mips
from esgcet.settings import BUILTIN_GENERICS, PROJECT_MAP

def check_files(files):
    for file in files:
        try:
            myfile = open(file, "r")
            myfile.close()
        except Exception as ex:
            publog.exception("Error opening file " + file + ". Exiting.")
            exit(1)


def read_exclude_vars_file(path):
    # one variable_id per line, '#' comments and blank lines ignored
    with open(path, "r") as fh:
        lines = [l.split("#", 1)[0].strip() for l in fh]
    return {l for l in lines if l}


def get_exclude_vars(pub, pub_args):
    # merges --exclude-variable, --exclude-variables-file, and config yaml equivalents
    exclude_vars = set(getattr(pub, "exclude_variable", None) or [])
    if getattr(pub, "exclude_variables_file", None):
        exclude_vars |= read_exclude_vars_file(pub.exclude_variables_file)
    try:
        cfg = pub_args.load_config(pub.cfg)
        exclude_vars |= set(cfg.get("exclude_variables", None) or [])
        if cfg.get("exclude_variables_file"):
            exclude_vars |= read_exclude_vars_file(cfg["exclude_variables_file"])
    except Exception:
        pass
    return exclude_vars


def dataset_id_from_mapfile(path):
    # first ' | '-delimited field of the first line; None on any problem (fail open)
    try:
        with open(path, "r") as fh:
            first_line = fh.readline()
        if not first_line or " | " not in first_line:
            return None
        return first_line.split(" | ")[0].strip()
    except Exception:
        return None


def is_excluded(dataset_id, exclude_vars):
    # exact dot-delimited DRS facet match, not substring
    if not dataset_id or not exclude_vars:
        return False
    return bool(exclude_vars.intersection(dataset_id.split(".")))

class PubRunner:

    def __init__(self, publog):
        self.log = publog
        self.proj = None

    def run(self, fullmap, pub_args):

    # SETUP
        split_map = fullmap.split("/")
        fname = split_map[-1]
        fname_split = fname.split(".")
        project_name = fname_split[0]

        files = []
        files.append(fullmap)

        check_files(files)

        argdict = pub_args.get_dict(project_name)

        if argdict["verbose"]:
            publog.info(argdict)
        if "proj" in argdict:
            project_name = argdict["proj"]
        else:
            argdict["proj"] = project_name
        project = project_name.lower()
        if project in PROJECT_MAP:
            project = PROJECT_MAP[project]
            argdict["project"] = project
            argdict["proj"] = project
        user_defined = False
        if argdict["user_project_config"]:
            user_defined = True
        non_netcdf = False
        if argdict["non_nc"]:
            non_netcdf = True

        if not self.proj:
            if project == "create-ip":
                from esgcet.create_ip import CreateIP
                proj = CreateIP(argdict)
            elif project == "cmip5":
                from esgcet.cmip5 import cmip5
                proj = cmip5(argdict)
            elif project == "input4mips":
                proj = input4mips(argdict)
            elif project == "e3sm" and not non_netcdf:
                from esgcet.e3sm import e3sm
                proj = e3sm(argdict)
            elif non_netcdf:
                proj = BasePublisher(argdict)
            elif user_defined or project in BUILTIN_GENERICS:
                proj = GenericPublisher(argdict)
            else:
                publog.error(
                    "Project "
                    + project
                    + " not supported.\nOpen an issue on our github to request additional project support."
                )
                exit(1)
            self.proj = proj
        # ___________________________________________
        # WORKFLOW - one line call

        self.proj.fullmap = fullmap
        return self.proj.workflow()


def get_log_file(pub_args, pub):
    # config-yaml-only (no CLI flag, same reasoning as disable_qaqc in
    # args.py): mirrors get_exclude_vars()'s defensive load pattern.
    try:
        cfg = pub_args.load_config(pub.cfg)
        return cfg.get("log_file", None)
    except Exception:
        return None


def main():
    pub_args = PublisherArgs()
    pub = pub_args.get_args()
    maps = pub.map  # full mapfile path
    if maps is None:
        publog.error(
            "Missing argument --map, use " + sys.argv[0] + " --help for usage."
        )
        exit(1)

    log_file = get_log_file(pub_args, pub)
    if log_file:
        logger.add_file_handler(log_file)
        publog.info(f"Logging to file: {log_file}")

    rc = True
    prunner = PubRunner(publog)
    exclude_vars = get_exclude_vars(pub, pub_args)
    if exclude_vars:
        publog.info("Excluding variable_id(s) from this run: " + ", ".join(sorted(exclude_vars)))

    def run_unless_excluded(mapfile_path):
        ds_id = dataset_id_from_mapfile(mapfile_path)
        if is_excluded(ds_id, exclude_vars):
            publog.info("Skipping excluded mapfile (dataset_id=" + str(ds_id) + "): " + mapfile_path)
            return True
        return prunner.run(mapfile_path, pub_args)

    for m in maps:
        if os.path.isdir(m):
            mappath = Path(m)
            files = os.listdir(m)
            for f in files:
                fullmappath = mappath / f
                if os.path.isdir(fullmappath):
                    continue  # Do not recurse subdirectories
                rc = rc and run_unless_excluded(str(fullmappath))
        else:
            myfile = open(m)
            ismap = False
            first = True
            for line in myfile:
                # if parsed line is not mapfile line, run on each file
                if first:
                    if "|" in line and (".v" in line or "#" in line):
                        ismap = True
                        break
                    first = False
                rc = rc and run_unless_excluded(line.rstrip())
            myfile.close()
            if ismap:
                rc = rc and run_unless_excluded(m)

    if not rc:
        exit(1)

    exit(0)


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
    main()
