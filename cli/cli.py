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
    self.log_level - уровень логирования tommano.log
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
        self.controller_provider = args.controller_provider
        self.forwarder_provider = args.forwarder_provider
        self.classifier_provider = args.classifier_provider
        if self.output_dir and not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        self.validate_only = args.validate_only
        self.log_level = args.log_level
        self.output_dict = translate(
            self.template_file,
            self.validate_only,
            self.controller,
            self.orchestrator,
            self.output_dir,
            self.log_level,
            self.controller_provider,
            self.forwarder_provider,
            self.classifier_provider,
        )
        if self.output_dir:
            with open(self.output_dir + TOPOLOGY_TPL_NAME, "w+") as f:
                yaml.dump(self.output_dict, f)
        else:
            print(yaml.dump(self.output_dict))

    def get_parser(self):
        parser = argparse.ArgumentParser(prog="tommano")
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
            default="clouni",
            choices=["clouni"],
            help="Translate to template supported by specific orchestrator",
        )
        parser.add_argument(
            "--controller",
            default="opendaylight",
            choices=["opendaylight"],
            help="Controller for vnffg",
        )
        parser.add_argument(
            "--controller-provider",
            default="ubuntu",
            choices=["ubuntu"],
            help="Provider operation system for OpenFlow controller",
        )
        parser.add_argument(
            "--classifier-provider",
            default="ubuntu",
            choices=["ubuntu"],
            help="Provider operation system for VNF classifiers",
        )
        parser.add_argument(
            "--forwarder-provider",
            default="ubuntu",
            choices=["ubuntu"],
            help="Provider operation system for VNF forwarders",
        )
        return parser


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    TranslatorCli(args)


if __name__ == "__main__":
    main()
