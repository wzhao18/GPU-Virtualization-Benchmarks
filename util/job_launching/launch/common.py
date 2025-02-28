from optparse import OptionParser
import subprocess
import re
import os
import yaml
import glob
import hashlib

this_directory = os.path.dirname(os.path.realpath(__file__)) + "/"

# Collapse long config name
long_config = {'INTRA_.*_LUT': 'INTRA_LUT'}

# Global variables
defined_apps = {}
defined_base_configs = {}
defined_extra_configs = {}


def load_defined_yamls():
    def parse_app_definition_yaml(def_yml):
        benchmark_yaml = yaml.load(open(def_yml), Loader=yaml.FullLoader)
        for suite in benchmark_yaml:
            for exe in benchmark_yaml[suite]['execs']:
                exe_name = list(exe.keys())[0]
                args_list = list(exe.values())[0]

                # replace data dir in args list with real path
                args_list = [args.replace("DATA",
                                          benchmark_yaml[suite]['data_dirs'])
                             if args else "" for args in
                             args_list]

                count = 0
                for args in args_list:
                    defined_apps[exe_name + "-" + str(count)] = (exe_name, args)
                    count += 1
        return

    def parse_config_definition_yaml(def_yml):
        configs_yaml = yaml.load(open(def_yml), Loader=yaml.FullLoader)
        for config in configs_yaml:
            if 'base_file' in configs_yaml[config]:
                defined_base_configs[config] = os.path.expandvars(
                    configs_yaml[config]['base_file'])
            elif 'extra_params' in configs_yaml[config]:
                # extra configs map store (regex -> params in text)
                defined_extra_configs[re.compile(config.replace('?', '(.*)'))] \
                    = configs_yaml[config]['extra_params']
        return

    define_yamls = glob.glob(os.path.join(this_directory, 'apps/define-*.yml'))
    for def_yaml in define_yamls:
        parse_app_definition_yaml(
            os.path.join(this_directory, 'apps', def_yaml))
    define_yamls = glob.glob(
        os.path.join(this_directory, 'configs/define-*.yml'))
    for def_yaml in define_yamls:
        parse_config_definition_yaml(
            os.path.join(this_directory, 'configs', def_yaml))


def parse_app_list(apps):
    # result is a two dimensional list: [[app1, app2], [app3], ...]
    results = [pair.split('+') for pair in apps]

    return results


def get_inputs_from_app(app, bench_home):
    if app in defined_apps:
        result = defined_apps[app][0] + ' ' + defined_apps[app][1]
        result = re.sub(r"\$BENCH_HOME", bench_home, result)
        return result
    else:
        return ''


def gen_configs_from_list(config_list):
    # Test to see if configs passed by users adhere to any defined configs i
    # and add them to the configurations to run/collect.
    def get_config(composed_name):
        tokens = composed_name.split('-')

        # base name determines which gpgpusim.config file to copy
        if tokens[0] not in defined_base_configs:
            print("Could not fined {0} in defined base names {1}".format(
                tokens[0], defined_base_configs))
            return None
        else:
            base_file = defined_base_configs[tokens[0]]

        # parse extra configs if any
        extra_config_text = ''
        found = False
        for token in tokens[1:]:
            for config_regex in defined_extra_configs.keys():
                matching = config_regex.search(token)
                if matching:
                    found = True
                    placeholder = matching.group(1).strip() \
                        if len(matching.groups()) > 0 else ''
                    params = defined_extra_configs[config_regex]\
                        .replace('?', placeholder)
                    extra_config_text += "\n#{0}\n{1}\n".format(token, params)

                    break

            if not found:
                print("Could not find {0} in defined extra configs {1}"
                      .format(token, defined_extra_configs))
                return None

        # collapse long configs
        for long_token in long_config:
            composed_name = re.sub(long_token, long_config[long_token],
                                   composed_name)

        return composed_name, base_file, extra_config_text

    results = [get_config(cfg) for cfg in config_list]

    return results


# This function exists so that this file can accept both
# absolute and relative paths. If no name is provided it sets the default
# Either way it does a test if the absolute path exists and if not,
# tries a relative path
def file_option_test(name, default, this_directory):
    if name == "":
        if default == "":
            return ""
        else:
            name = os.path.join(this_directory, default)
    try:
        with open(name):
            pass
    except IOError:
        name = os.path.join(os.getcwd(), name)
        try:
            with open(name):
                pass
        except IOError:
            exit("Error - cannot open file {0}".format(name))
    return name


def dir_option_test(name, default, this_directory):
    if name == "":
        name = os.path.join(this_directory, default)
    if not os.path.isdir(name):
        name = os.path.join(os.getcwd(), name)
        if not os.path.isdir(name):
            exit("Error - cannot open file {0}".format(name))
    return name


def get_run_dir(parent_run_dir, launch_name):
    return os.path.join(parent_run_dir, 'run-' + launch_name)


def get_log_dir(parent_run_dir):
    return os.path.join(parent_run_dir, 'logfiles')


