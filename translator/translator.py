import os

import yaml
import logging
import sys
import translator.utils as utils

from toscaparser.tosca_template import ToscaTemplate
from translator.template import ToscaNormativeTemplate

VNF_DEF_PATH = '/definitions/VNF_types/'
NFV_DEF_PATH = '/definitions/NFV_definintion_1_0.yaml'
TOSCA_DEF_PATH = '/definitions/TOSCA_definition_1_0.yaml'
MAP_PATH = '/definitions/TOSCA_NFV_mapping'
PROJECT_NAME = 'nfv_tosca_translator'


def translate(template_file, validate_only, orchestrator, provider, log_level='info'):
    """
        Функция трансляции шаблонов TOSCA NFV в TOSCA NORMATIVE
        Вход:
        template_file - путь к файлу с исходным шаблном в нотации TOSCA NFV
        validate_only -  true, если нужно только валидировать шаблон
        log_level='info' - уровень логирования nfv_tosca_translator.log
        Выход:
        output_dict - yaml dict итогового шаблона
        generated_scripts - dict of lists строк ansible скриптов для настройки compute узлов
        Принцип работы:
        1) читаем файл template_file в yaml dict
        2) добавляем imports с файлами NFV_definition_1_0.yaml и TOSCA_definition_1_0.yaml в которых содержатся описания
        типов узлов и отношений
        3) вызываем tosca-parser для валидации шаблона, если validate_only то возвращаем сообщение об успехе/ошибке и
        пустой dict generated_scripts
        4) читаем файл маппинга в yaml dict
        5) вызываем конструктор класса транслятора
        6) возвращаем результат обработки транслятором
    """
    log_map = dict(
        debug=logging.DEBUG,
        info=logging.INFO,
        warning=logging.WARNING,
        error=logging.ERROR,
        critical=logging.ERROR
    )
    MAP_PATH = '/definitions/TOSCA_NFV_mapping_' + orchestrator + '.yaml'
    logging_format = "%(asctime)s %(levelname)s %(message)s"
    logging.basicConfig(filename=os.path.join(utils.get_project_root_path() + "/", 'nfv_tosca_translator.log'),
                        filemode='a', level=log_map[log_level],
                        format=logging_format, datefmt='%Y-%m-%d %H:%M:%S')
    with open(template_file, "r") as f:
        try:
            tpl = yaml.load(f, Loader=yaml.SafeLoader)
            logging.info("Template successfully loaded from file.")
        except yaml.scanner.ScannerError as e:
            logging.error("Error parsing TOSCA template: %s %s." % (e.problem, e.context_mark))
            sys.exit(1)
    tosca_def = utils.get_project_root_path() + TOSCA_DEF_PATH
    nfv_def = utils.get_project_root_path() + NFV_DEF_PATH
    if 'imports' in tpl:
        if isinstance(tpl['imports'], list):
            tpl['imports'].append(tosca_def)
            tpl['imports'].append(nfv_def)
            logging.info("Imports added to template.")
        else:
            logging.error("Error parsing imports in TOSCA template.")
            sys.exit(1)
    else:
        tpl['imports'] = []
        tpl['imports'].append(tosca_def)
        tpl['imports'].append(nfv_def)
        logging.info("Imports added to template.")

    try:
        tosca_parser_tpl = ToscaTemplate(yaml_dict_tpl=tpl)
    except:
        logging.exception("Got exception from OpenStack tosca-parser.")
        sys.exit(1)

    if validate_only:
        logging.info("Template successfully passed validation.")
        tpl = {"template successfully passed validation": template_file}
        return tpl, {}

    map_file = utils.get_project_root_path() + MAP_PATH
    with open(map_file, "r") as f:
        try:
            mapping = yaml.load(f, Loader=yaml.SafeLoader)
            logging.info("Mapping successfully loaded from file.")
        except yaml.scanner.ScannerError as e:
            logging.error("Error parsing NFV mapping: %s %s." % (e.problem, e.context_mark))
            sys.exit(1)

    try:
        tosca_normative_tpl = ToscaNormativeTemplate(tosca_parser_tpl=tosca_parser_tpl, yaml_dict_mapping=mapping,
                                                     orchestrator=orchestrator, provider=provider)
        logging.info("Template successfully passed translation to normative TOSCA.")
    except:
        logging.exception("Got exception on translating NFV to TOSCA.")
        sys.exit(1)
    return tosca_normative_tpl.get_result()
