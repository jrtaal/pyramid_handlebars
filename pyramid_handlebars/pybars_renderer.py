from pyramid.i18n import get_localizer


import pyramid.path

import pybars

from pybars_helpers import helpers as handlebars_helpers
from handlebars_i18n import translate_handlebars, compile_template
from lifeshare.lib.renderers import localize_dict, stackdict

import os
import threading
import logging
logger = logging.getLogger("lifeshare.rendering.pybars")


class LocalizedLazyTemplateLoader(dict):
    def __init__(self, factory, localizer = None):
        dict.__init__(self)
        self.fac = factory
        self.localizer = localizer

    def __getitem__(self, item):
        try:
            return self.fac.get_compiled_template(item + ".bar", self.localizer)
        except KeyError: #pragma: no cover
            raise
        except Exception,e: #pragma: no cover
            logger.exception("Could not get template %s", item)
            raise KeyError

class PybarsRendererFactory:

    _compiler_registry = threading.local()
    _templates = {}
    _helpers = {}
    _partials = {}

    def __init__(self, info):
        self.info = info
        self._helpers = handlebars_helpers

        pkg,self.assetpath = self.info.settings['pybars.directories'].split(":")
        self.assetresolver = pyramid.path.AssetResolver(pkg)


        reload = self.info.settings['reload_templates']
        self.reload = (reload in (True, "true", "True","1",1,"yes" ,"Yes"))
        if self.reload:
            logger.debug("Force reload templates at file change")
        self.localized = self.info.settings.get('pybars.localize', False)

        if self.localized:
            self.localized_assetpath = self.info.settings['pybars.localized_directories']

        self.reload = reload

        self.js_auto_compile = self.info.settings.get('pybars.js_auto_compile', False)
        self.js_path = self.info.settings.get('pybars.js_compiled_directory', None)

        
    def __call__(self, value, system):
        dd = stackdict(system)
        dd.push(value)
        localizer = get_localizer(system['request'])
        if self.localized:
            dd = localize_dict(localizer, dd)

        partials = LocalizedLazyTemplateLoader(self, localizer)
        return unicode(self.get_compiled_template(self.info.name, localizer)(dd, helpers = self._helpers, partials = partials))


    @classmethod
    def get_threadsafe_compiler(cls):
        if not hasattr(cls._compiler_registry, 'compiler'):
            cls._compiler_registry.compiler = pybars.Compiler();
        return cls._compiler_registry.compiler

    def get_compiled_template(self, name, localizer):
        locale = localizer.locale_name or "default"
        #import pdb;pdb.set_trace()
        try:
            template = self._templates[name]
        except KeyError:
            pass
        else:
            localized = template[locale]
            if ( self.reload and 
                ( localized['path'] and localized['timestamp'] < os.path.getmtime(localized['path']) or 
                     ( template['path'] and os.path.getmtime(localized['path']) < os.path.getmtime(template['path'])) ) ): 
                logger.info("Template from cache is outdated, force reload %s < %s ",
                            localized['timestamp'],
                            os.path.getmtime(localized['path'])) 
            else:
                return localized['compiled']

        original_asset = self.assetresolver.resolve(os.path.join(self.assetpath, name))
        if not self.localized:
            localized_asset = original_asset
            template_body = unicode(original_asset.stream().read().decode("utf-8"))

        else:
            #localized_asset = self.assetresolver.resolve(os.path.join(self.localized_assetpath, localizer.locale_name, name))
            localized_asset = self.assetresolver.resolve(os.path.join(self.localized_assetpath, localizer.locale_name, name))
            if ( not os.path.exists(localized_asset.abspath()) or os.path.getmtime(localized_asset.abspath()) < os.path.getmtime(original_asset.abspath())):
                logger.info("Translating template %s", name)

                original_asset = self.assetresolver.resolve(os.path.join(self.assetpath, name))
                original = unicode(original_asset.stream().read().decode("utf-8"))
                template_body = translate_handlebars(original, localizer, None)
                path = localized_asset.abspath()
                if not os.path.isdir(os.path.dirname(path)):
                    os.mkdir(os.path.dirname(path))
                f = open(localized_asset.abspath(), "w")
                try:
                    logger.info(u"Translating template with locale %s:\n%s\n\t->\n%s", locale, original, template_body)
                    f.write(template_body.encode("utf-8"))
                    f.close()
                except:
                    logger.exception("Could not write translated file to %s", localized_asset.abspath())
                    
                if self.js_auto_compile:
                    logger.info("Compiling template")
                    compile_template(localized_asset.abspath(), os.path.join(self.js_path, localizer.locale_name, os.path.dirname(name)))
            else:
                template_body= unicode(localized_asset.stream().read().decode("utf-8"))

        compiler = self.get_threadsafe_compiler()
        template_compiled = compiler.compile(template_body);

        self._templates.setdefault(name, dict())
        self._templates[name].update( { 'path' : original_asset.abspath(),
                                        locale : dict(compiled = template_compiled,
                                                      path = localized_asset.abspath(), 
                                                      timestamp = os.path.getmtime(localized_asset.abspath())) 
                                        })
        logger.log(5,"Template cache: %s", self._templates[name])

        return template_compiled
