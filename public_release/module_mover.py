import re
from importlib import import_module
from modulefinder import ModuleFinder
import inspect
import os
from shutil import rmtree
import logging

from artemis.general.should_be_builtins import detect_duplicates, izip_equal

from Routines.Debugger import Debugger

Debugger()
# logging.basicConfig()
LOGGER = logging.getLogger('export-demo')
LOGGER.setLevel(logging.WARNING)


def get_src_file(module):
    return module.__file__[:-1] if module.__file__.endswith('.pyc') else module.__file__


def get_module_import_dict(object, scope = 'project', remove_packages = False, whole_proj=None):
    """
    Given some code object (or the full name of a module), find all the modules that must be imported for this object to
    run.
    :param object:
    :param scope: One of:
        'package': Only collect modules from same root package (eg root package of foo.bar.baz is foo.
        'project': Only collect modules in same project (ie, modules whose root package is in the same directoy as object's root package)
        'all': Collect all dependent modueles (not recommended, as this will, for example include a bunch of numpy code).
    :return: A dict<module_name: module_path>
    """
    # LOGGER.setLevel(logging.DEBUG)
    LOGGER = logging.getLogger('export-demo-get_module_import_dict')
    assert scope in ('package', 'project', 'all')
    if isinstance(object, (list, tuple)):
        dicts, names = zip(*[get_module_import_dict(ob, scope=scope) for ob in object])
        return {k: v for d in dicts for k, v in iter(d.items())}, names
    elif isinstance(object, str):
        module = import_module(object)
        LOGGER.warning(("module is", module))
    else:
        module = inspect.getmodule(object)
    module_file = get_src_file(module)
    LOGGER.warning(("got module_file", module_file))
    finder = ModuleFinder()
    this_package = module.__name__.split('.')[0]
    LOGGER.warning(("got this_package", this_package))
    LOGGER.info('Scanning Dependent Modules in {}.  This may take some time...'.format(this_package))
    finder.run_script(module_file)

    module_files = {name: get_src_file(module) for name, module in iter(finder.modules.items()) if module.__file__ is not None}
    LOGGER.warning(("got these module_files: module_files", module_files))
    module_files[module.__name__] = get_src_file(module)  # Don't forget yourself!
    LOGGER.warning(("got this module_files[module.__name__]", module_files[module.__name__]))
    # module_files =
    if scope=='package':
        module_files = {name: mod for name, mod in iter(module_files.items()) if name.split('.')[0]==this_package}
        LOGGER.warning(("as this is a package scope module_files", module_files))
    elif scope=='project':
        base_dir = whole_proj if whole_proj else os.path.dirname(os.path.dirname(module.__file__))
        LOGGER.warning(("as this is a project scope base dir is", base_dir))
        LOGGER.warning(("as this module.__file__ is", module.__file__))
        if whole_proj:
            new_module_files = {}
            LOGGER.warning(("we will iterate thought ", module_files.items()))
            for name, mod in iter(module_files.items()):
                if re.search(whole_proj, mod, re.IGNORECASE):
                    new_module_files[name] = mod
            module_files = new_module_files
        else:
            module_files = {name: mod for name, mod in iter(module_files.items()) if mod.startswith(base_dir)}
        LOGGER.warning(("as this is a project scope module_files are ", module_files))
    #todo: for some reason find 27 modules, but copy only some of them
    LOGGER.info('Scan Complete.  {} dependent modules found.'.format(len(module_files)))
    # module_name_to_module_path = {name: get_src_file(m) for name, m in iter(module.items())}
    if remove_packages:
        LOGGER.warning(("removing packages"))
        LOGGER.warning(("before remove module_files are", module_files))
        module_files = {name: path for name, path in iter(module_files.items()) if not (path.endswith('__init__.py') or path.endswith('__init__.pyc'))}
        LOGGER.warning(("after remove module_files are ", module_files))
    return module_files, module.__name__


def copy_modules_to_dir(object, destination_dir, root_package, search_whole_proj=None, code_subpackage=None, helper_subpackage ='helpers', scope='project', clear_old_package = False):
    """
    An offline version of the package
    Given some code object (or the full name of a module), find all the modules that must be imported for this object to
            run.
    :param object:
    :param destination_dir:
    :param root_package: how should be resulting dir called
    :param search_whole_proj: if the module is deeply in some project which should be thoroughly imported (use the "project" scope)
    :param code_subpackage:
    :param helper_subpackage: how to call the folder where all helpers will lie
    :param scope: One of:
            'package': Only collect modules from same root package (eg root package of foo.bar.baz is foo.
            'project': Only collect modules in same project (ie, modules whose root package is in the same directoy as object's root package)
            'all': Collect all dependent modueles (not recommended, as this will, for example include a bunch of numpy code).
    :param clear_old_package:
    :return:
    """
    modules, names = get_module_import_dict(object, scope=scope, whole_proj=search_whole_proj)

    LOGGER = logging.getLogger('export-demo-copy_modules_to_dir')
    if isinstance(names, str):
        names = [names]
    root_dir = os.path.join(destination_dir, root_package)

    if clear_old_package and os.path.exists(root_dir):
        rmtree(root_dir)

    code_dir = root_dir if code_subpackage is None else os.path.join(root_dir, code_subpackage)
    code_module_name = root_package if code_subpackage is None else root_package+'.'+code_subpackage
    helper_module_name = root_package if helper_subpackage is None else root_package+'.'+helper_subpackage


    helper_dir = root_dir if helper_subpackage is None else os.path.join(root_dir, helper_subpackage)

    for direct in (root_dir, code_dir, helper_dir):
        try:
            os.makedirs(direct)
        except OSError:
            pass
        with open(os.path.join(direct, '__init__.py'), 'w') as f:
            f.write('')

    old_name_to_new_name = {module_name: code_module_name+'.'+module_name.split('.')[-1] if module_name in names else helper_module_name+'.'+module_name.split('.')[-1] for module_name in modules.keys()}
    LOGGER.warning(("Old_to_new_name: ", old_name_to_new_name))
    duplicates = {k: v for (k, v), isdup in izip_equal(iter(old_name_to_new_name.items()), detect_duplicates(old_name_to_new_name.values())) if isdup}
    if len(duplicates)>0:
        raise Exception('There is a collision between two or more modules names: {}\n.  You need to rename these modules to have unique names.'.format(duplicates))

    old_name_to_new_path = {module_name: os.path.join(code_dir, os.path.split(module_file)[1]) if module_name in names else os.path.join(helper_dir, os.path.split(module_file)[1]) for module_name, module_file in iter(modules.items())}
    LOGGER.warning(("Old_to_new_path: ", old_name_to_new_path))

    LOGGER.warning(("iterating_over iter(modules.items()): ", iter(modules.items()).__next__()))
    for module_name, module_path in iter(modules.items()):
        LOGGER.warning(("iterating_over module_name, module_path: ", module_name, module_path))
        _, file_name = os.path.split(module_path)

        with open(module_path) as f:
            txt = f.read()

        for dep_module_name, new_module_name in iter(old_name_to_new_name.items()):
            LOGGER.warning(
                ("iterating_over dep_module_name:", dep_module_name, new_module_name))
            #should replace the strings to new module name
            txt = txt.replace('\nfrom {} import '.format(dep_module_name), '\nfrom {} import '.format(new_module_name))
            txt = txt.replace('\nimport {}'.format(dep_module_name), '\nimport {}'.format(new_module_name))

            txt = txt.replace('import {}'.format(dep_module_name), 'import {}'.format(new_module_name))
            txt = txt.replace('from {} import '.format(dep_module_name), 'from {} import '.format(new_module_name))

        with open(old_name_to_new_path[module_name], 'w') as f:
            f.write(txt)

        LOGGER.info('Copied {} -> {}'.format(module_path, old_name_to_new_path[module_name]))


if __name__ == '__main__':
    #copy_modules_to_dir('artemis.plotting.demo_dbplot', '/Users/peter/projects/tests/artemistest5', root_package='dbplot_demo', clear_old_package=True)
    copy_modules_to_dir('ML.Segmentation.Keras.Unet.model_self_pretr_train_flow',
                        'C:/Users/ebara/OneDrive/Skoltech/Projects/Pythons_project/Pycharm/Pythons_dev/test_pub',
                        scope='package',
                        root_package='test', clear_old_package=True)