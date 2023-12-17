import logging
import pathlib

import pkg_resources

from mopidy import config, ext

__version__ = pkg_resources.get_distribution("Mopidy-HearthisSimple").version

logger = logging.getLogger(__name__)


class Extension(ext.Extension):
    dist_name = "Mopidy-HearthisSimple"
    ext_name = "hearthissimple"
    version = __version__

    def get_default_config(self):
        return config.read(pathlib.Path(__file__).parent / "ext.conf")

    def get_config_schema(self):
        schema = super().get_config_schema()
        schema["username"] = config.Secret()
        schema["password"] = config.Secret()
        return schema

    def setup(self, registry):
        from .backend import HearthisSimpleBackend

        registry.add("backend", HearthisSimpleBackend)
