'''
Created on 3 mei 2012

@author: jacco
'''

import unittest
import os

from lifeshare.lib.renderers import stackdict
from lifeshare.lib.renderers.ajax_renderer import  AjaxRendererFactory
from lifeshare.lib.renderers.pybars_renderer import PybarsRendererFactory
from pyramid import testing
from pyramid.threadlocal import get_current_registry
from pyramid.i18n import TranslationStringFactory

class RendererInfoFixture(object):
    def __init__(self, name, registry):
        self.registry = registry
        self.settings = registry.settings
        self.name = name
        self.package = self

class RendererTest(unittest.TestCase):
    
    def setUp(self):
        from ..test import settings
        from sqlalchemy.ext.declarative import declarative_base

        settings['pybars.directories'] = "lifeshare.lib.test:templates"
        settings['osiris.store.sqla_base'] = declarative_base()

        config = testing.setUp(settings=settings)
        self.config = config

        
        #self.config.include('lifeshare.app')
        #self.config.include('lifeshare.api.api')
        self.config.add_translation_dirs('lifeshare:locale')
        config.add_renderer('.bar', 'lifeshare.lib.renderers.pybars_renderer.PybarsRendererFactory')

        import lifeshare.templates.deps as template_deps
        
        def  master_get_globals():
            return {}

        ajax_template_factory = AjaxRendererFactory(
                                   dependencies = template_deps.deps, 
                                   get_globals = master_get_globals)

        ajax_master_template_factory = AjaxRendererFactory( master ="jsbase.bar",
                                   dependencies = template_deps.deps, 
                                   get_globals = master_get_globals)

        config.add_renderer('.ajax', ajax_master_template_factory)
        config.add_renderer('ajax', ajax_master_template_factory)
        
        #config.add_renderer('.ajax-nomaster', ajax_template_factory)
        self.registry = get_current_registry()
        #self.registry.settings["pybars.directories"] = "lifeshare:templates/handlebars"
    
    def tearDown(self):
        testing.tearDown()
        

    def test_types(self):
        sd = stackdict({'a':1,'b':2})
        sd['c']=3
        self.assertEqual(sd['a'], 1)
        self.assertEqual(sd['b'], 2)
        self.assertEqual(sd['c'], 3)

        sd.push( dict(a = 9, d=4))
        self.assertEqual(sd['a'], 9)
        self.assertEqual(sd['d'], 4)
        sd.pop()
        self.assertEqual(sd['a'], 1)
    
        self.assertEqual(set(sd.keys()), set(['a','b','c']))

        self.assertEqual(set(sd.iterkeys()), set(['a','b','c']))

        self.assertEqual(set(sd.iteritems()), set([ ('a', 1),('b', 2),('c',3)]))

    def get_request(self):
        request = testing.DummyRequest()
        from lifeshare.lib.renderers.acceptparse import AnnotatedMIMEAccept
        import time
        request.accept = AnnotatedMIMEAccept("text/html")
        request._request_time = time.time()
        return request

    def test_pybars(self):
        request = self.get_request()
        
        renderer = PybarsRendererFactory(RendererInfoFixture("test.bar", self.registry))
        
        response = renderer( {"value1": "Test Value", "value2" : ["Value 2a", "Value 2b"], "value3" : u"Videos\xc3" } , 
                             dict(request=request, registry = self.registry))
        #print ">" + response + "<"
        self.assertEqual(response,
u"""Begin Child
 Value 1:
 Test Value
 Value 2:
 
 - Value 2a
 
 - Value 2b
 
 Videos\xc3
End Child
""")

    def test_ajaxrenderer(self):
        from lifeshare.templates.deps import deps

        def get_globals(request):
            return {}

        factory = AjaxRendererFactory("test_master.bar", deps, get_globals = get_globals)
        renderer = factory(RendererInfoFixture("test.bar.ajax", self.registry))
        request = self.get_request()
        request.is_xhr = False
        request.user = None
        system = dict(request = request, registry = self.registry )
        response = renderer({ "title" : "Test Title", "preamble":"", 
                              "body": "BODY", "resource": {  "value1": "Test Value", "value2" : ["Value 2a", "Value 2b"],
                                                             "value3" : u"BLA\xc0" }} , system)
        #print ">" + response + "<"
        self.assertEqual(response , 
u"""Master

Title: Test Title

Begin Body
Begin Child
 Value 1:
 Test Value
 Value 2:
 
 - Value 2a
 
 - Value 2b
 
 BLA\xc0
End Child

End Body
End Master
""")

    def test_path(self):
        pass
        
    def test_ajaxjson(self):
        from lifeshare.templates.deps import deps

        def get_globals(request):
            return {}

        data = { "title" : "Test Title", "preamble":"", 
                              "body": "BODY", "resource": {  "value1": "Test Value", "value2" : ["Value 2a", "Value 2b"],
                                                             "value3" : u"BLA\xc0" }}
        factory = AjaxRendererFactory("test_master.bar", deps, get_globals = get_globals)
        renderer = factory(RendererInfoFixture("test.bar.ajax", self.registry))
        request = self.get_request()
        request.is_xhr = True
        request.view_name = "json"
        request.user = None
        system = dict(request = request, registry = self.registry )
        response = renderer( data  , system)

        self.assertEqual(response ,
"""{"body": "BODY", "path": "/", "preamble": "", "resource": {"value3": "BLA\\u00c0", "value2": ["Value 2a", "Value 2b"], "value1": "Test Value"}, "title": "Test Title"}""")

        request.view_name = "test"
        response = renderer( data, system)

        self.assertEqual(str(response), """Master

Title: Test Title

Begin Body
<pre>{'body': 'BODY',
 'path': '/',
 'preamble': '',
 'resource': {'value1': 'Test Value', 'value2': ('Value 2a', 'Value 2b'), 'value3': u'BLA\\xc0'},
 'title': 'Test Title'}</pre>
End Body
End Master
""")


        request.view_name = "ajax"
        response = renderer( data, system)
        #print ">" + response + "<"

        self.assertEqual(str(response), """{"body": "Begin Child\\n Value 1:\\n Test Value\\n Value 2:\\n \\n - Value 2a\\n \\n - Value 2b\\n \\n BLA\u00c0\\nEnd Child\\n", "resource": {"value3": "BLA\u00c0", "value2": ["Value 2a", "Value 2b"], "value1": "Test Value"}, "title": "Test Title", "path": "/", "preamble": ""}""")


        request.view_name = "ajaxp"
        response = renderer( data, system)
        #print ">" + response + "<"

        self.assertEqual(str(response), """load({"body": "Begin Child\\n Value 1:\\n Test Value\\n Value 2:\\n \\n - Value 2a\\n \\n - Value 2b\\n \\n BLA\\u00c0\\nEnd Child\\n", "resource": {"value3": "BLA\\u00c0", "value2": ["Value 2a", "Value 2b"], "value1": "Test Value"}, "title": "Test Title", "path": "/", "preamble": ""})""")

        request.view_name = "ajaxtest"
        response = renderer( data, system)

        #print ">" + response + "<"
        self.assertEqual(str(response), """{'body': u'Begin Child\\n Value 1:\\n Test Value\\n Value 2:\\n \\n - Value 2a\\n \\n - Value 2b\\n \\n BLA\\xc0\\nEnd Child\\n',\n 'path': '/',\n 'preamble': '',\n 'resource': {'value1': 'Test Value', 'value2': ('Value 2a', 'Value 2b'), 'value3': u'BLA\\xc0'},\n 'title': 'Test Title'}""")


    def test_i18n_bars(self):

        renderer = PybarsRendererFactory(RendererInfoFixture("i18ntest.bar", self.registry))

        _ = TranslationStringFactory("Lifeshare")

        for locale in ("nl", "en") :
            request = self.get_request()

            request._LOCALE_ = locale
            response = renderer( {"n": 1, "o": 2, "a" : ["1","2",_("Video")], "b" : ["1","2",_("Videos")], "NAME" :  "Jacco" } , dict(request=request, registry = self.registry))
            #print "LOCALE", locale
            #print response
            if locale in  ("nl", "nl_NL"):
                self.assertEqual(response[0:20], u"Welkom bij Lifeshare")
            if locale in  ("en", "en_US"):
                self.assertEqual(response[0:20], u"Welcome to Lifeshare")
        #self.assertEqual(response[0:8] , "Value 1:")

    def test_subdir_template(self):
        import pdb; pdb.set_trace()
        request = self.get_request()
        renderer = PybarsRendererFactory(RendererInfoFixture("test_embed.bar", self.registry))
        
        response = renderer( {"value1": "Test Value", "value2" : ["Value 2a", "Value 2b"], "value3" : u"Videos\xc3" } , 
                             dict(request=request, registry = self.registry))
        print response
        
    def test_localize_template(self):
        from lifeshare.lib.renderers.handlebars_i18n import extract_handlebars, translate_handlebars
        from pyramid.i18n import get_localizer

        tmp = open(os.path.join(os.path.dirname(__file__), "templates/i18ntest.bar"))
        strings = extract_handlebars(tmp,[],[],{})
                
        self.assertEqual(strings[1][2], u"English")
        self.assertEqual(strings[2][2], u"Dutch")

        tmp.seek(0)
        request = self.get_request()
        request._LOCALE_ = "nl"

        localizer = get_localizer(request)

        tmp2 = translate_handlebars(tmp.read(), localizer, "Lifeshare")

        self.assertEqual(tmp2[0:114], """Welkom bij Lifeshare
<div class="row-fluid">
    <div class="span4">EngelsNederlands</div>
    <div class="span8">""")
