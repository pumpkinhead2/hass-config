# -*- coding: UTF-8 -*-
import logging
import click
import pretty_cron
import ast
import sys
import json
import ipaddress

from pprint import pformat as pf
from typing import Any

if sys.version_info < (3, 4):
    print("To use this script you need python 3.4 or newer, got %s" %
          sys.version_info)
    sys.exit(1)

import miio  # noqa: E402

_LOGGER = logging.getLogger(__name__)
pass_dev = click.make_pass_decorator(miio.Device, ensure=True)


def validate_ip(ctx, param, value):
    if value is None:
        return value
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError as ex:
        raise click.BadParameter("Invalid IP: %s" % ex)


def validate_token(ctx, param, value):
    if value is None:
        return value
    token_len = len(value)
    if token_len != 32:
        raise click.BadParameter("Token length != 32 chars: %s" % token_len)
    return value

class CLI:
    @click.group(invoke_without_command=True)
    @click.option('--ip', envvar="MIROBO_IP", callback=validate_ip)
    @click.option('--token', envvar="MIROBO_TOKEN", callback=validate_token)
    @click.option('-d', '--debug', default=False, count=True)
    @click.option('--id-file', type=click.Path(dir_okay=False, writable=True),
                  default='/tmp/python-mirobo.seq')
    @click.version_option()
    @click.pass_context
    def cli(ctx, ip: str, token: str, debug: int, id_file: str):
        """A tool to command Xiaomi Vacuum robot."""
        if debug:
            logging.basicConfig(level=logging.DEBUG)
            _LOGGER.info("Debug mode active")
        else:
            logging.basicConfig(level=logging.INFO)

        # if we are scanning, we do not try to connect.
        if ctx.invoked_subcommand == "discover":
            ctx.obj = "discover"
            return
        return

        if ip is None or token is None:
            click.echo("You have to give ip and token!")
            sys.exit(-1)

        start_id = manual_seq = 0
        try:
            with open(id_file, 'r') as f:
                x = json.load(f)
                start_id = x.get("seq", 0)
                manual_seq = x.get("manual_seq", 0)
                _LOGGER.debug("Read stored sequence ids: %s" % x)
        except (FileNotFoundError, TypeError) as ex:
            _LOGGER.error("Unable to read the stored msgid: %s" % ex)
            pass

        vac = miio.Vacuum(ip, token, start_id, debug)

        vac.manual_seqnum = manual_seq
        _LOGGER.debug("Connecting to %s with token %s", ip, token)

        ctx.obj = vac

        #if ctx.invoked_subcommand is None:
        #    ctx.invoke(status)
        #    cleanup(vac, id_file=id_file)


    @cli.resultcallback()
    @pass_dev
    def cleanup(vac: miio.Vacuum, **kwargs):
        if vac.ip is None:  # dummy Device for discovery, skip teardown
            return
        id_file = kwargs['id_file']
        seqs = {'seq': vac.raw_id, 'manual_seq': vac.manual_seqnum}
        _LOGGER.debug("Writing %s to %s" % (seqs, id_file))
        with open(id_file, 'w') as f:
            json.dump(seqs, f)

if __name__ == "__main__":

    CLI.cli()
