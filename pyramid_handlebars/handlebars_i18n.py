import logging 
import collections
from pymeta.grammar import OMeta

Token = collections.namedtuple('Token',['typ','value','line','column'])

logger = logging.getLogger("lib.pybars")
#logger.setLevel(logging.DEBUG)

grammar = r"""
hspace ::= (' ' | '\t')
template ::=  (<text> | <translatecommand>|<handlebarscommand>)*:body => ['template', body]
body ::= (<text>|<handlebarscommand>)*:body => body
handlebarscommand ::= <hs_start><hs_body>:body<hs_stop> => ('handlebars', body)
hs_start ::= '{' '{'
hs_stop ::= '}' '}'
hs_body ::= (~(<hs_stop>) <anything>)+:body => u"".join(body)
text ::= (~(<start>) <anything>)+:text => ('literal', u''.join(text))
start ::= '{' <Tcommand>:comm '{' => comm
stop ::= '}' <Tcommand>:comm '}' 
Tcommand ::= ('_'|'P'|'p'):command => ('tcommand', 'translate' if command=='_' else 'pluralize')  
translatecommand ::= <start>:comm<argumentcl>:arg((<comma> <argumentcl>)*):args<stop> => (comm[1], [arg] + args, get_line_col(self.input))  
argumentcl ::= (<namedargument>|<posargument>):arg => arg
fooargument ::= (~(<stop>) ~(<comma>) <stringorquotedstring>)*:arg => u"".join(arg)
argument ::= (<stringorquotedstring>):arg => arg
posargument ::= (<handlebarscommand>|<argument>):arg => ('', arg)
namedargument ::= <hspace>*<symbol>:left <is> <argument>:right => (left, right)
symbol ::= (<letterOrDigit>|'_'|'@')+:symbol => u"".join(symbol)
quotedstring ::= <hspace>*(<singleqs>|<doubleqs>):str<hspace>* => str 
singleqs ::= ("'":q (~"'" <anything>)*:stra "'") => u"".join(stra)
doubleqs ::= ('"':q (~'"' <anything>)*:stra '"') => u"".join(stra)
stringorquotedstring ::= (<quotedstring>| (~(<stop>) ~(<comma>)<anything>))*:s => u"".join(s)
comma ::= ','
is ::= '='
"""

def get_line_col(input):
    #print type(input.data)
    lines = unicode("".join(input.data)).split("\n")
    position = input.position
    counter = 0
    lineNo = 1
    columnNo = 0
    for line in lines:
        newCounter = counter + len(line)
        if newCounter > position:
            columnNo = position - counter
            break
        else:
            counter += len(line) + 1
            lineNo += 1
    return lineNo, columnNo, [line]

_tl = OMeta.makeGrammar(grammar, {'get_line_col': get_line_col}, 'handlebars')

def parse_tree(tree, level = 0, localizer = None, default_domain = None):
    body = []
    ts = []
    from pyramid.i18n import TranslationStringFactory
    TranslationString = TranslationStringFactory(default_domain)
    for node in tree:
        if node[0] == 'template':
            ts_, body_ = parse_tree(node[1], level+1, localizer, default_domain)
            ts.extend(ts_), body.extend(body_)
        if node[0] == 'literal':
            body.append(node[1])
        if node[0] == 'handlebars':
            body.append(node[1])
        if node[0] in ( 'translate','pluralize'):
            #print node
            args = node[1]
            lineno,col, linetext = node[2]
            posargs = [arg[1] for arg in args if not arg[0]]
            kwargs = dict( [(arg[0],arg[1]) for arg in args if arg[0] ])
            domain = kwargs.pop('domain',default_domain)
            default = kwargs.pop('default',None)
            default_single = kwargs.pop('default_single',None)
            default_plural = kwargs.pop('default_plural', None)
            deferred = False
            for i,arg in enumerate(posargs):
                if isinstance(arg, tuple) and arg[0]=='handlebars':
                    deferred = True
                    posargs[i] = arg[1]
                    # Do a deferred translate (at template rendering)
            if node[0] == 'translate' and len(posargs) == 1:
                if localizer:
                    if deferred:
                        body.append("{{I18N %s %s}}" % (posargs[0], " ".join( ("%s=%s" % (k,v) for k,v in kwargs.iteritems() ) ) ))
                    else:
                        _ts = TranslationString(posargs[0],default = default, mapping = kwargs)
                        body.append(localizer.translate(_ts))
                        #body.append(localizer.translate(posargs[0], default = default, domain = domain, mapping = kwargs))
                else:
                    body.append(args[0])
                if domain:
                    ts.append((lineno, "dugettext", (domain, posargs[0]), linetext ))
                else:
                    ts.append((lineno, "ugettext", posargs[0], linetext ))

            if node[0] == 'pluralize' and len(posargs) == 3:
                if localizer:
                    _s = TranslationString( posargs[0], default = default_single)
                    _p = TranslationString( posargs[1], default = default_plural)
                    if deferred:
                        #_s = localizer.pluralize( posargs[0], posargs[1], 1,  domain = domain, mapping = kwargs)
                        #_p = localizer.pluralize( posargs[0], posargs[1], 2,  domain = domain, mapping = kwargs)
                        _ss = localizer.pluralize( _s, _p, 1, domain = domain, mapping = kwargs)
                        _pp = localizer.pluralize( _s, _p, 2, domain = domain, mapping = kwargs)
                        body.append('{{Pluralize "%s" "%s" %s}}' % ( _ss.replace('"','\\"').replace("'",'\''), 
                                                                     _pp.replace("'",'\'').replace('"','\\"'), posargs[2]))
                    else:
                        #body.append(localizer.pluralize( posargs[0], posargs[1], int(posargs[2]), domain = domain, mapping = kwargs))
                        body.append(localizer.pluralize( _s, _p, int(posargs[2]), domain = domain, mapping = kwargs))
                else:
                    if deferred:
                        pass#body.append(posargs[1] if (int(posargs[2]) > 0) else posargs[0] )
                    else:
                        body.append(posargs[1] if (int(posargs[2]) > 0) else posargs[0] )                  
                if domain:
                    ts.append((lineno, "dngettext", (domain, posargs[0], posargs[1]), linetext))
                else:
                    ts.append((lineno, "ungettext", (posargs[0],posargs[1]), linetext))

    return ts, body

def extract_handlebars(fileobj, keywords, comment_tags, options):
    """Extract messages from Handlebars files.

    :param fileobj: the file-like object the messages should be extracted from
    :param keywords: a list of keywords (i.e. function names) that should be recognized as translation functions
    :param comment_tags: a list of translator tags to search for and include in the results
    :param options: a dictionary of additional options (optional)
    :return: an iterator over ``(lineno, funcname, message, comments)`` tuples
    :rtype: ``iterator``
    """


    s = fileobj.read().decode("utf-8")
    tree = _tl(s).apply('template')

    items, body =  parse_tree(tree)
    return items


import gettext

def translate_handlebars(s, localizer, default_domain):
    tree = _tl(s).apply('template')
    items, body = parse_tree(tree,  localizer = localizer, default_domain = default_domain)
    return u"".join(body)


import os
from subprocess import Popen
from distutils import log as distlog
from distutils.core import Command

from pyramid.i18n import make_localizer

class translate_templates(Command):#pragma: no cover
    description = "translate all templates"

    user_options = [ ('locales=', 'l', "which locales to use"),
                     ('templatedomain=', 't', 'which domain to assign to translations') ,
                     ('input-dir=', 'i', 'path to input templates' ),
                     ('output-dir=','o', 'path to output templates' ),
                     ('locale-dir=', None, 'path to local files' )
                     ]

    def run(self):
        #srcpath = os.path.abspath(os.path.join('lifeshare','templates','handlebars'))
        #dstpath = os.path.abspath(os.path.join('lifeshare','templates','translated'))
        self.translate_templates(self.input_dir, self.output_dir)

    def initialize_options(self):
        self.locales = ["nl"]
        self.templatedomain = "pyramid_i18n"
        self.input_dir = "templates/"
        self.output_dir = "templates/translated"
        self.locale_dir = "locale/"

    def finalize_options(self):
        self.locales = self.locales.split()

    def _translate_templates(self, path, destpath, localizer, default_domain):
        tmps = os.listdir(path)
        if not os.path.exists(destpath):
             os.mkdir(destpath)
        for tmp in tmps:
            nm,ext = os.path.splitext(tmp)
            if os.path.isdir(os.path.join(path, tmp)):
                self._translate_templates(os.path.join(path, tmp), os.path.join(destpath, tmp), localizer, default_domain)
                continue
            if not ext == ".bar":
                continue
            in_ = file(os.path.join(path,tmp)).read().decode("utf-8")
            distlog.info("Translating %s to %s", tmp, destpath)
            tr = translate_handlebars(in_, localizer, default_domain)
            open(os.path.join(destpath,tmp),"w").write(tr.encode("utf-8"))
            

    def translate_templates(self,srcpath, destpath):
        if not os.path.exists(destpath):
             os.mkdir(destpath)
        localepath = os.path.abspath(self.locale_dir)
        for locale in self.locales:
            _destpath = os.path.join(destpath, locale)
            #print localepath
            #translations = gettext.translation('Lifeshare', localepath, [locale], codeset="utf8")
            #print translations
            #localizer = Localizer(locale, translations)
            localizer = make_localizer(locale, [localepath])
            #print localizer

            distlog.info("Translating files in %s to %s", os.path.join(srcpath) , os.path.join(_destpath))
            self._translate_templates(srcpath, _destpath, localizer, default_domain = self.templatedomain)


def compile_template(infile, out_path, minify = True):
    pth, nm = os.path.split(infile)
    nm, ext = os.path.splitext(nm)
    if not os.path.isdir(out_path):
        os.mkdir(out_path)
    out = os.path.join(out_path, nm +".js")
    cmd = [os.path.join("./", "node_modules", "handlebars", "bin", "handlebars") , infile, "-f", out] 
    logger.info("Compiling : %s", " ".join(cmd))
    pr = Popen( cmd ) 
    pr.wait()

    if minify:
        out = os.path.join(out_path, nm +".min.js")
        cmd = [os.path.join("./", "node_modules", "handlebars", "bin",  "handlebars") , "-m", infile, "-f", out] 
        logger.info("Compiling : %s", " ".join(cmd))
        pr = Popen( cmd ) 
        pr.wait()
    return True


class compile_templates(Command):
    description = "Compile all templates"

    user_options = [ ('locales=', 'l',"which locales to use"),
                     ('input-dir=', None, 'path to input templates' ),
                     ('output-dir=', None, 'path to output templates' ),
                     ('compiler=', None, 'path to compilers'),
                     ]

    def run(self):
        srcpath = os.path.abspath(self.input_dir)
        dstpath = os.path.abspath(self.output_dir)

        for locale in self.locales:
            distlog.info("Compiling templates for locale %s", locale)
            srcpath = os.path.abspath(os.path.join(self.input_dir, locale))
            _destpath = os.path.join(dstpath,locale )
            if not os.path.exists(dstpath):
                os.mkdir(dstpath)
            self.compile_templates(srcpath,_destpath)

    def initialize_options(self):
        self.locales = ["en"]
        self.input_dir = "templates/translated"
        self.output_dir = "templates/compiled"
        self.compiler = "../node_modules/handlebars/bin/handlebars"

    def finalize_options(self):
        self.locales = self.locales.split()

    def compile_templates(self, srcpath, destpath):
        self._compile_templates(srcpath, destpath)

    def _compile_templates(self, srcpath, destpath):
        tmps = os.listdir(srcpath)
        distlog.info("Templates: %s", tmps)
        _tmps = []
        if not os.path.exists(destpath):
            os.mkdir(destpath)
        for tmp in tmps:
            nm,ext = os.path.splitext(tmp)
            if os.path.isdir(os.path.join(srcpath, tmp)):
                distlog.info("Checking path %s", os.path.join(srcpath, tmp))
                self._compile_templates( os.path.join(srcpath, tmp), os.path.join(destpath, tmp))
                continue
            if not ext == ".bar":
                 continue
            _tmps.append(tmp)
            
            src = os.path.join(srcpath, tmp) 
            dst = os.path.join(destpath, nm + ".js") 
            #distlog.info("Checking %s %s %s", dst, os.stat(src).st_mtime , os.stat(dst).st_mtime)
            if not os.path.exists(dst) or os.stat(src).st_mtime > os.stat(dst).st_mtime:
                distlog.info("Compiling %s to %s", src, dst)
                cmd = [self.compiler ,   src, "-f", dst] 
                distlog.info("CMD: %s",  " ".join(cmd))
                pr = Popen( cmd ) 
                pr.wait()

            dst = os.path.join(destpath, nm + ".min.js")
            if not os.path.exists(dst) or os.stat(src).st_mtime > os.stat(dst).st_mtime:
                distlog.info("Compiling with minify %s to %s", src, dst)
                cmd = [self.compiler ,  "-m", src , "-f", dst] 
                distlog.debug("CMD: %s",  " ".join(cmd))
                pr = Popen( cmd ) 
                pr.wait()

class setup_templates(Command):
    def run(self):
        # Run all relevant sub-commands.  This will be some subset of:
        #  - build_py      - pure Python modules
        #  - build_clib    - standalone C libraries
        #  - build_ext     - Python extensions
        #  - build_scripts - (Python) scripts
        for cmd_name in self.get_sub_commands():
            self.run_command(cmd_name)

    user_options = []
    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    sub_commands = [('translate_templates',  None),
                    ('compile_templates',  None),
                   ]
        
if __name__ == "__main__":
    import sys
    file = open(sys.argv[1])
    items = extract_handlebars(file,[],[],[])
    print "ITEMS"
    print "\n".join((str(it[0:3]) for it in items))

    locale = "nl_NL"

    pth = os.path.abspath(os.path.join('lifeshare','locale'))
    print pth
    translations = gettext.translation('Lifeshare', pth, ['nl'], codeset="utf8")
    print translations
    #localizer = Localizer("nl_NL", translations)
    localizer = make_localizer(locale, [pth])
    print localizer

    file.seek(0)
    default_domain = None
    body = translate_handlebars(file.read(), localizer, default_domain )
    print body
