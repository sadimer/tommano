import argparse
import sys
import yaml
import os

from translator.translator import translate

TOPOLOGY_TPL_NAME = "/topology.yaml"


class TranslatorCli(object):
    """
    Класс запуска трансляции из командной строки
    Вход: массив argv
    Атрибуты:
    self.template_file - путь к файлу с исходным шаблном в нотации TOSCA NFV
    self.output_dir - путь к директории в которой будет лежать итоговый шаблон topology.yaml и скрипты ansible
    self.validate_only - true, если нужно только валидировать шаблон
    self.output_dict - yaml dict итогового шаблона
    self.generated_scripts - dict of lists строк ansible скриптов для настройки compute узлов
    self.log_level - уровень логирования nfv_tosca_translator.log
    Принцип работы:
    1) парсим аргументы командной строки
    2) вызываем функцию translate для преобразования шаблона
    3) получаем yaml шаблон и ansible скрипты и записываем результат в файлы
    """

    def __init__(self, argv):
        parser = self.get_parser()
        (args, args_list) = parser.parse_known_args(argv)
        self.template_file = os.getcwd() + "/" + args.template_file
        self.output_dir = args.output_dir
        self.orchestrator = args.orchestrator
        self.controller = args.controller
        self.provider = args.provider
        if self.output_dir and not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        self.validate_only = args.validate_only
        self.log_level = args.log_level
        self.output_dict, self.basic_scripts, self.vnf_scripts = translate(
            self.template_file,
            self.validate_only,
            self.controller,
            self.orchestrator,
            self.provider,
            self.output_dir,
            self.log_level,
        )
        self.basic_scripts.update(self.vnf_scripts)
        if self.output_dir:
            with open(self.output_dir + TOPOLOGY_TPL_NAME, "w+") as f:
                yaml.dump(self.output_dict, f)
            for key, script in self.basic_scripts.items():
                with open(self.output_dir + "/" + key, "w+") as ouf:
                    for line in script:
                        print(line, file=ouf, end="")
        else:
            print(yaml.dump(self.output_dict))
            for key, script in self.basic_scripts.items():
                print("\n" + key + ":")
                for line in script:
                    print(line, end="")

    def get_parser(self):
        parser = argparse.ArgumentParser(prog="nfv_tosca_translator")
        parser.add_argument(
            "--template-file",
            metavar="<filename>",
            required=True,
            help="YAML TOSCA NFV template to parse",
        )
        parser.add_argument(
            "--validate-only",
            action="store_true",
            default=False,
            help="Only validate input NFV template, do not perform translation",
        )
        parser.add_argument(
            "--output-dir",
            metavar="<dirname>",
            required=False,
            help="Output dir for TOSCA normative template and configure scripts",
        )
        parser.add_argument(
            "--log-level",
            default="info",
            choices=["debug", "info", "warning", "error", "critical"],
            help="Set log level for tool",
        )
        parser.add_argument(
            "--orchestrator",
            default="nfv",
            choices=["nfv", "clouni"],
            help="Translate to template supported by specific orchestrator",
        )
        parser.add_argument(
            "--controller",
            default="opendaylight",
            choices=["opendaylight"],
            help="Controller for vnffg",
        )
        parser.add_argument(
            "--provider",
            default="cumulus",
            choices=["cumulus", "ubuntu"],
            help="Translate to template supported by specific vnf provider",
        )
        return parser


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    TranslatorCli(args)


if __name__ == "__main__":
    main()
