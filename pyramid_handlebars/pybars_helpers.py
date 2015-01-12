from pybars import strlist
from pybars._compiler import Scope

from ..repr import pformat

import logging
logger = logging.getLogger("lifeshare.rendering.helpers")

ROOT = "/api/1.0/"

from pyramid.traversal import resource_path

def URLHelper(this, arg=None, route="", args=[]):
    """transforms a url event into the right URL 
    """
    #req=get_current_request()
    if arg==None:
        arg = this
    _resource_path = resource_path(arg) 
   
    return ROOT + _resource_path + ( "/".join(args) if args else "" ) 

def HandlerHelper(this, event, **kwargs):
    """transforms a url event into the right URL 
    """
    return event.onhandler()

def PaginateHelper(this, options):
    result = strlist()
    count = int(this['resource_index_info']['last_pageno'])
    if count>0:
        for i in range(count):
            scope = Scope(dict(pageid = i, active = (i==this["page"]), pageno = str(i+1), index=this['index'] ), this)
            #this["pageid"] = i
            #this['active'] = (i==this["this_pageid"])
            #this["pageno"] = str(i+1) # Human counting page 1, page 2...
            result.grow(options['fn'](scope))
            #del this["pageid"]
            #del this["pageno"]
            #del this["active"]
    return result

def PageURLHelper(this, arg=None, route="", args=None, **kwargs):
    uri = URLHelper(this.parent.parent, None, route=route, args=args)
    perpage = int(this.parent.parent['resource_index_info']['perpage'])
    try:
        page = int(this['pageid'])
    except:
        page = 0
    if "perpage" in kwargs:
        perpage = int(kwargs["perpage"])
    if "page" in kwargs:
        page = int (kwargs["page"])
    #strip page and perpage:
    parts = uri.split("/")
    newparts = []
    i=0
    while i < len(parts):
        part = parts[i]
        if part in ('page', 'perpage' ):
            i+=2
            continue
        newparts.append(part)
        i+=1
    uri = "/".join(newparts)
    if perpage != int(this.parent.parent['resource_index_info']['default_perpage']) :
        uri += "/perpage/%d" % perpage
    if page > 0 :
        uri += "/page/%d" % page

    return uri

def AsHelper(this, options, a, b):
    ctxt = this
    while hasattr(ctxt, 'context'):
        ctxt = ctxt.context
    ctxt[str(b)] = a
    result = options['fn'](this)
    del ctxt[str(b)]
    return result
    
def TraceHelper(this, value):
    raise Exception("Debug statement found in context = %s: %s" % (this, value))

def DebugHelper(this, item):
    logger.debug("Value of item is %s", item) 
    return pformat(item)

def RangeHelper(this, options, name, begin, end):
    result = strlist()
    if begin<end:
        for i in range(begin, end):
            this[name] = i
            result.grow(options['fn'](this))
        del this[name]
    return result

def JoinHelper(this, options, context, inter):
    result = strlist()
    if hasattr(context, "iteritems"):
        context = context.itervalues()
    first = True
    for local_context in context:
        scope = Scope(local_context, this)
        if not first:
            result.grow(inter)
            first = False
        result.grow(options['fn'](scope))
    return result

from operator import __add__, __sub__, __mul__, __div__
def MathHelper(this, type_, op, *args):
    tpe = {"int": int, "float":float}[type_]
    operator = {"add": __add__, "sub": __sub__, "mul": __mul__, "div": __div__}[op]
    return tpe(reduce(operator, map(tpe, args)))

def PluralizeHelper(this, singleton, plural, n):
    if int(n)>1:
        return plural
    else:
        return singleton

def I18NHelper(this, message):
    """Should return a translated version of message, given the current locale
    TODO: implement
    """
    return message

def PlayerHelper(this, **kwargs):
    dd = {}
    dd.update(this['player_params'])
    dd.update(kwargs)
    logger.debug("%s: replace global %s, local %s", this['player_html_str'],  this['player_params'], kwargs) 
    return this['player_html_str'] % dd


def RenderHelper(this, options, arg=None,**kwargs):

    if not arg:
       arg = this
    scope = Scope(arg,this)
    scope.context.update(kwargs)
    body = options['fn'](scope)
    scope.context.update(body = body)

    func = options['partials'][scope['template']]
    return func(scope, helpers = options['helpers'], partials = options['partials'])

helpers = dict( [ ( nm[0:-6], hlpr) for (nm, hlpr) in globals().items() if nm.endswith("Helper") ] )
__all__ = [ nm for (nm, hlpr) in globals().items() if nm.endswith("Helper") ]
__all__.append("helpers")
