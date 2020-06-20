#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def get_local_test_settings_file(argv):
    assert argv[1] == "test"
    assert "manage.py" in argv[0]

    local_settings_dir = os.path.join(os.path.split(argv[0])[0], "local_settings")

    from django.core.management import CommandParser, CommandError

    parser = CommandParser(
            usage="%(prog)s subcommand [options] [args]",
            add_help=False)

    parser.add_argument('--local_test_settings',
                        dest="local_test_settings")

    options, args = parser.parse_known_args(argv)

    if options.local_test_settings is None:
        local_settings_file = "local_settings_example.py"
    else:
        local_settings_file = options.local_test_settings

    if os.path.split(local_settings_file)[0] == "":
        local_settings_file = os.path.join(
            local_settings_dir, local_settings_file)

    if os.path.abspath(local_settings_file) == os.path.abspath(
            os.path.join(local_settings_dir, "local_settings.py")):
        raise CommandError(
            "Using production local_settings for tests is not "
            "allowed due to security reason."
        )

    if not os.path.isfile(local_settings_file):
        raise CommandError(
            "file '%s' does not exist" % local_settings_file
        )

    return local_settings_file


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'latex2image.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    if sys.argv[1] == "test":
        local_settings_file = get_local_test_settings_file(sys.argv)
        os.environ['L2I_LOCAL_TEST_SETTINGS'] = local_settings_file

    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
