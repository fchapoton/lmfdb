# -*- coding: utf-8 -*-
import math
# from Lfunctionutilities import pair2complex, splitcoeff, seriescoeff
from sage.all import *
import sage.libs.lcalc.lcalc_Lfunction as lc
import re
import pymongo
import bson
from lmfdb.utils import parse_range, make_logger
logger = make_logger("DC")
from lmfdb.modular_forms.elliptic_modular_forms.backend.web_modforms import *
from WebNumberField import WebNumberField
try:
    from dirichlet_conrey import *
except:
    logger.critical("dirichlet_conrey.pyx cython file is not available ...")
from HeckeCharacters import *

def lmfdb_ideal2label(ideal):
      """
      labeling convention for ideal f:
      use two elements representation f = (n,b)
      with n = f cap Z an integer
       and b an algebraic element sum b_i a^i
      label f as n.b1+b2*a^2+...bn*a^n
      (dot between n and b, a is the field generator, use '+' and )
      """
      a,b = ideal.gens_two()
      s = '+'.join( '%s*a**%i'%(b,i) for i,b in enumerate(b.polynomial().list())
                                    if b != 0 ) 
      return "%s.%s"%(a,b)

def lmfdb_label2ideal(k,label):
      if label.count('.'):
          n, b = label.split(".")
      else:
          n, b = label, '0'
      a = k.gen()
      n, b = eval(n), eval(b)
      n, b = k(n), k(b)
      return k.ideal( (n,b) )

def lmfdb_ideal2tex(ideal):
    a,b = ideal.gens_two()
    return "\langle %s, %s\\rangle"%(a._latex_(), b._latex_())

def lmfdb_hecke2label(chi):
    """
    label of Hecke character
    """
    return '.'.join(map(str,chi.exponents()))

def lmfdb_hecke2tex(chi):
    """
    label of Hecke character
    """
    return r'\(\chi_{%s}(\cdot)\)'%(','.join(map(str,chi.exponents())))

def lmfdb_label2hecke(label):
    """
    label of Hecke character
    """
    return map(int,label.split('.'))

def lmfdb_dirichlet2tex(mod,num):
    return r'\(\chi_{%s}(%s,\cdot)\)'%(mod,num)

def lmfdb_bool(b):
    return ("No","Yes")[b]

def latex_char_logvalue(x, tag=False):
    n = int(x.numer())
    d = int(x.denom())
    if d == 1:
        s = "1"
    elif n == 1 and d == 2:
        s = "-1"
    elif n == 1 and d == 4:
        s = "i"
    elif n == 3 and d == 4:
        s = "-i"
    else:
        s = r"e\left(\frac{%s}{%s}\right)" % (n, d)
    if tag:
        return "\(%s\)" % s
    else:
        return s

def latex_tuple(v):
    if len(v) == 1:
        return v[0]
    else:
        return "(%s)" % (', '.join(v))


def log_value(modulus, number):
    """
    return the list of values of a given Dirichlet character
    """
    from dirichlet_conrey import DirichletGroup
    G = DirichletGroup_conrey(modulus)
    chi = G[number]
    l = []
    for j in range(1, modulus + 1):
        if gcd(j, modulus) != 1:
            l.append('0')
        else:
            logvalue = chi.logvalue(j)
            l.append(latex_char_logvalue(logvalue, True))
    return l

#############################################################################
###
###    Class for Web objects
###
#############################################################################

class WebCharObject:
    """ class for all characters and character groups """
    def __init__(self, args):
        self._keys = [ 'title', 'credit', 'codelangs', 'type',
                 'nf', 'nflabel', 'nfpol', 'modulus', 'modlabel',
                 'number', 'numlabel', 'texname', 'codeinit', 'symbol',
                 'previous', 'prevmod', 'prevnum', 'next', 'nextmod',
                 'nextnum', 'structure', 'codestruct', 'conductor',
                 'condlabel', 'codecond', 'isprimitive', 'inducing',
                 'indlabel', 'codeind', 'order', 'codeorder', 'parity',
                 'isreal', 'generators', 'codegen', 'genvalues', 'logvalues',
                 'values', 'codeval', 'galoisorbit', 'codegalois',
                 'valuefield', 'vflabel', 'vfpol',
                 'kerfield', 'kflabel', 'kfpol', 'contents' ]   
        self.type = args.get('type',None)
        self.nflabel = args.get('number_field',None)
        self.modlabel = args.get('modulus',None)
        self.numlabel = args.get('number',None)

        self._compute()

    def _compute(self):
        pass

    def to_dict(self):
        d = {}
        for k in self._keys:
            d[k] = getattr(self,k,None)
            if d[k] == None:
                pass # should not
        return d

    @staticmethod
    def texlogvalue(x, tag=False):
        if not isinstance(x, Rational):
            return 1
        n = int(x.numer())
        d = int(x.denom())
        if d == 1:
            s = "1"
        elif n == 1 and d == 2:
            s = "-1"
        elif n == 1 and d == 4:
            s = "i"
        elif n == 3 and d == 4:
            s = "-i"
        else:
            s = r"e\left(\frac{%s}{%s}\right)" % (n, d)
        if tag:
            return "\(%s\)" % s
        else:
            return s

    @staticmethod
    def textuple(l,tag=True):
        t = ','.join(l)
        if len(l) > 1: t='(%s)'%t
        if tag: t = '\(%s\)'%t
        return t

    @staticmethod
    def texbool(b):
        return ("No","Yes")[b]

#############################################################################
###  Dirichlet type

class WebDirichlet(WebCharObject):
    """ 
    For some applications (orbits, enumeration), Dirichlet characters may be
    represented by a couple (modulus, number) without computing the Dirichlet
    group.
    """

    def _char_desc(self, num, mod=None, prim=None):
        """ usually num is the number, but can be a character """
        if isinstance(num, DirichletCharacter_conrey):
            mod = num.modulus()
            num = num.number()
        elif mod == None:
            mod = self.modulus
        if prim == None:
            prim = self.charisprimitive(mod,num)
        return ( mod, num, self.char2tex(mod,num), prim)

    def charisprimitive(self,mod,num):
        if isinstance(self.G, DirichletGroup_conrey) and self.G.modulus()==mod:
            G = self.G
        else:
            G = DirichletGroup_conrey(mod)
        return G[num].is_primitive()

    """ for Dirichlet over Z, everything is described using integers """
    @staticmethod
    def char2tex(modulus, number, val='\cdot', tag=True):
        c = r'\chi_{%s}(%s,%s)'%(modulus,number,val)
        if tag:
           return '\(%s\)'%c
        else:
           return c

    group2tex = int
    group2label = int
    label2group = int

    ideal2tex = int
    ideal2label = int
    label2ideal = int

    """ numbering characters """
    number2label = int
    label2number = int
    
    @property
    def groupelts(self):
        return map(self.group2tex, self.Gelts)

    def _compute_Gelts(self):
        self.Gelts = []
        m,n = self.modulus, 1
        for k in xrange(1,m):
            if gcd(k,m) == 1:
                self.Gelts.append(k)
                n += 1
                if n > self.maxcols: break




#############################################################################
###  Hecke type

class WebHecke(WebCharObject):
    """ FIXME design issue: should underlying group elements be represented
        by tuples or by ideals ? for computations tuples are much better,
        currently a mix of these is done """

    def _compute(self):
        self.k = self.label2nf(self.nflabel)
        self._modulus = self.label2ideal(self.k, self.modlabel)
        self.G = G = RayClassGroup(self.k, self._modulus)
        self.H = H = self.G.dual_group()
        #self.number = lmfdb_label2hecke(self.numlabel)
        # make this canonical
        self.modlabel = self.ideal2label(self._modulus)
        self.credit = "Pari, Sage"
        self.codelangs = ('pari', 'sage')

    """ labeling conventions are put here """

    @staticmethod
    def char2tex(c):
        """ c is a Hecke character """
        number = c.exponents()
        return r'\(\chi_{%s}(\cdot)\)'%(','.join(map(str,number)))

    def _char_desc(self, c, modlabel=None, prim=None):
        """ c is a Hecke character of modulus self.modulus
            unless modlabel is specified
        """
        if modlabel == None:
            modlabel = self.modlabel
        numlabel = self.number2label( c.exponents() )
        if prim == None:
            prim = c.is_primitive()
        return (modlabel, numlabel, self.char2tex(c), prim ) 

    @staticmethod
    def ideal2tex(ideal):
        a,b = ideal.gens_two()
        return "\(\langle %s, %s\\rangle\)"%(a._latex_(), b._latex_())
    @staticmethod
    def ideal2label(ideal):
        """
        labeling convention for ideal f:
        use two elements representation f = (n,b)
        with n = f cap Z an integer
         and b an algebraic element sum b_i a^i
        label f as n.b1+b2*a^2+...bn*a^n
        (dot between n and b, a is the field generator, use '+' and )
        """
        a,b = ideal.gens_two()
        s = '+'.join( '%s*a**%i'%(b,i) for i,b in enumerate(b.polynomial().list())
                                      if b != 0 ) 
        return "%s.%s"%(a,b)
    @staticmethod
    def label2ideal(k,label):
        """ k = underlying number field """
        if label.count('.'):
            n, b = label.split(".")
        else:
            n, b = label, '0'
        a = k.gen()
        # FIXME: dangerous
        n, b = eval(n), eval(b)
        n, b = k(n), k(b)
        return k.ideal( (n,b) )

    """ underlying group contains ideals ( or could be exponent tuples) """
    group2tex = ideal2tex
    group2label = ideal2label
    label2group = label2ideal

    @staticmethod
    def number2label(number):
        return '.'.join(map(str,number))

    @staticmethod
    def label2number(label):
        return map(int,label.split('.'))


    # FIXME: replace by calls to WebNF
    @staticmethod
    def label2nf(label):
        x = var('x')
        pol = eval(label)
        return NumberField(pol,'a')

    def _compute_Gelts(self):
        self.Gelts = []
        c = 1
        for x in self.G.iter_exponents():
            self.Gelts.append(x)
            c += 1
            if c > self.maxcols: break

#############################################################################
###  Family

class WebCharFamily(WebCharObject):
    """ compute first groups """
    def __init__(self, args):
        WebCharObject.__init__(self,args)
        self._keys = [ 'title', 'credit', 'codelangs', 'type', 'nf', 'nflabel',
            'nfpol', 'codeinit', 'headers', 'contents' ]   
        self.headers = [ 'label', 'order', 'structure' ]
        self._contents = []

    def add_row(self, G):
        self.contents.append(
                 (G.modlabel,
                  G.texname,
                  G.order,
                  G.structure) )

#############################################################################
###  Groups

class WebCharGroup(WebCharObject):
    """
    Class for presenting Character Groups on a web page
    self.H is the character group
    self.G is the underlying group
    """
    def __init__(self, args):
        self.headers = [ 'order', 'primitive']
        self.Gelts = []
        self.contents = []
        self.maxrows = 25
        self.maxcols = 20
        WebCharObject.__init__(self,args)
        self._keys = [ 'title', 'credit', 'codelangs', 'type', 'nf', 'nflabel',
            'nfpol', 'modulus', 'modlabel', 'texname', 'codeinit', 'previous',
            'prevmod', 'next', 'nextmod', 'structure', 'codestruct', 'order',
            'codeorder', 'generators', 'codegen', 'valuefield', 'vflabel',
            'vfpol', 'headers', 'groupelts', 'contents' ] 

    @property
    def structure(self):
        inv = self.G.invariants()
        return '\(%s\)'%('\\times '.join(['C_{%s}'%d for d in inv]))
    @property
    def codestruct(self):
        return [('sage','G.invariants()'), ('pari','G.cyc')]

    @property
    def order(self):
        return self.G.order()
    @property
    def codeorder(self):
        return [('sage','G.order()'), ('pari','G.no')]

    @property
    def modulus(self):
        return self.ideal2tex(self._modulus)

    @property
    def generators(self):
        return self.textuple(map(self.group2tex, self.G.gens()), tag=False)

    @property
    def groupelts(self):
        return map(self.group2tex, self.Gelts)

    def add_row(self, chi):
        prim = chi.is_primitive()
        self.contents.append(
                 ( self._char_desc(chi, prim=prim),
                   ( chi.multiplicative_order(),
                     self.texbool(prim) ),
                     self.charvalues(chi) ) )
     
    def _fill_contents(self):
        self._compute_Gelts()
        r = 0
        for c in self.H:
            self.add_row(c)
            r += 1
            if r > self.maxrows:
                break

    def charvalues(self, chi):
        return [ self.texlogvalue(chi.logvalue(x), tag=True) for x in self.Gelts ]


#############################################################################
###  Characters

class WebChar(WebCharObject):
    """
    Class for presenting a Character on a web page
    """

    @property
    def order(self):
        return self.chi.order()

    @property
    def isprimitive(self):
        return self.texbool( self.chi.is_primitive() )

    @property
    def isreal(self):
        return self.texbool( self.order <= 2 )

    @property
    def conductor(self):
        return self.ideal2tex(self.chi.conductor())

    @property
    def modulus(self):
        return self.ideal2tex(self._modulus)

    @property
    def texname(self):
        return self.char2tex(self.chi)

    @property
    def condlabel(self):
        return self.ideal2label(self.conductor)

    @property
    def inducing(self):
        return self.char2tex(self.conductor, self.indlabel)


    @property
    def valuefield(self):
        """ compute order """
        order2 = self.order
        if order2 % 4 == 2:
            order2 = order2 / 2
        if order2 == 1:
            vf = r'\(\mathbb{Q}\)'
        elif order2 == 4:
            vf = r'\(\mathbb{Q}(i)\)'
        else:
            vf = r'\(\mathbb{Q}(\zeta_{%d})\)' % order2
        self._order2 = order2
        return vf

    @property
    def vflabel(self):
      _ = self.valuefield # make sure valuefield was computed
      order2 = self._order2
      if order2 == 1:
          return '1.1.1.1'
      elif order2 == 4:
          return '2.0.4.1'
      valuewnf =  WebNumberField.from_cyclo(order2)
      if not valuewnf.is_null():
          return valuewnf.label
      else:
          return ''

#############################################################################
###  Actual web objects used in lmfdb

class WebDirichletGroup(WebCharGroup, WebDirichlet):

    #def __init__(self, args):
    #    WebCharGroup.__init__(self, args)

    def _compute(self):
        self.modulus = m = int(self.modlabel)
        self.H = H = DirichletGroup_conrey(m)
        self.H_sage = H.standard_dirichlet_group()
        self._fill_contents()
        self.credit = 'Sage'
        self.codelangs = ('pari', 'sage')
        
    @property
    def codeinit(self):
        return [('sage', 'H = DirichletGroup_conrey(m)\n' +
                         'H_sage = H.standard_dirichlet_group()'),
                ('pari', 'G = znstar(m)') ]

    @property
    def title(self):
      return r"Dirichlet Group modulo %s" % (self.modulus)

    @property
    def generators(self):
        return self.textuple(map(str, self.H_sage.unit_gens()))
    @property
    def codegen(self):
        return [('sage', 'H_sage.unit_gens()'),
                ('pari', 'G.gen') ]

    @property
    def structure(self):
        inv = self.H_sage.generator_orders()
        return '\(%s\)'%('\\times '.join(['C_{%s}'%d for d in inv]))
    @property
    def codestruct(self):
        return [('sage', 'H_sage.generator_orders()'),
                ('pari', 'G.cyc') ]
      
    @property
    def order(self):
        return self.H_sage.order()

class WebDirichletCharacter(WebDirichlet, WebChar):

    def _compute(self):
        self.modulus = m = int(self.modlabel)
        self.G = G = DirichletGroup_conrey(m)
        self.G_sage = G_sage = G.standard_dirichlet_group()
        self._gens = G_sage.unit_gens()
        self.number = n = int(self.numlabel)

        assert gcd(m, n) == 1
        self.chi = chi = G[n]
        self.chi_sage = chi_sage = chi.sage_character()
        self.order = chi.multiplicative_order()
        self.credit = "Sage"
        self.codelangs = ('pari', 'sage')
        self.prevmod, self.prevnum = prev_dirichlet_char(m, n)
        self.nextmod, self.nextnum = next_dirichlet_char(m, n)

    @property
    def title(self):
        return r"Dirichlet Character %s" % (self.texname)

    @property
    def texname(self):
        return self.char2tex(self.modulus, self.number)

    @property
    def previous(self):
        return self.char2tex(self.prevmod, self.prevnum)

    @property
    def next(self):
        return self.char2tex(self.nextmod, self.nextnum)

    @property
    def indlabel(self):
        """ Conrey scheme makes this trivial ? except at two..."""
        #return self.number % self.conductor
        indlabel =  self.chi.primitive_character().number()
        if indlabel == 0:
            return 1
        return indlabel
    
    @property
    def parity(self):
        return ('Odd', 'Even')[self.chi.is_even()]

    @property
    def generators(self):
        return self.textuple(map(str, self._gens) )

    @property
    def genvalues(self):
        logvals = [self.chi.logvalue(k) for k in self._gens]
        return self.textuple( map(self.texlogvalue, logvals) )

    @property
    def galoisorbit(self):
        order = self.order
        mod, num = self.modulus, self.number
        prim = self.isprimitive
        orbit = [ power_mod(num, k, mod) for k in xrange(1, order) if gcd(k,order) == 1 ]
        return [ self._char_desc(num, prim=prim) for num in orbit ]

    @property
    def symbol(self):
        """ chi is equal to a kronecker symbol if and only if it is real """
        if self.order != 2:
            return None
        cond = self.conductor
        if cond % 2 == 1:
            if cond % 4 == 1: m = cond
            else: m = -cond
        elif cond % 8 == 4:
            if cond % 16 == 4: m = cond
            elif cond % 16 == 12: m = -cond
        elif cond % 16 == 8:
            if self.chi.is_even(): m = cond
            else: m = -cond
        else:
            return None
        return r'\(\displaystyle\left(\frac{%s}{\bullet}\right)\)' % (m)

    def gauss_sum(self, val):
        val = int(val)
        mod, num = self.modulus, self.number
        chi = self.chi.sage_character()
        g = chi.gauss_sum_numerical(100, val)
        real = round(g.real(), 10)
        imag = round(g.imag(), 10)
        if imag == 0.:
            g = str(real)
        elif real == 0.:
            g = str(imag) + "i"
        else:
            g = latex(g)
        from sage.rings.rational import Rational
        x = Rational('%s/%s' % (val, mod))
        n = x.numerator()
        n = str(n) + "r" if not n == 1 else "r"
        d = x.denominator()
        Gtex = '\mathbb{Z}/%s\mathbb{Z}' % mod
        chitex = self.char2tex(mod, num, tag=False)
        chitexr = self.char2tex(mod, num, 'r', tag=False)
        deftex = r'\sum_{r\in %s} %s e\left(\frac{%s}{%s}\right)'%(Gtex,chitexr,n,d)
        return r"\(\displaystyle \tau_{%s}(%s) = %s = %s. \)" % (val, chitex, deftex, g)

    def jacobi_sum(self, val):
        mod, num = self.modulus, self.number
        val = int(val[0])
        psi = self.G[val]
        chi = self.chi.sage_character()
        psi = psi.sage_character()
        jacobi_sum = chi.jacobi_sum(psi)
        chitex = self.char2tex(mod, num, tag=False)
        psitex = self.char2tex(mod, val, tag=False)
        Gtex = '\mathbb{Z}/%s\mathbb{Z}' % mod
        chitexr = self.char2tex(mod, num, 'r', tag=False)
        psitex1r = self.char2tex(mod, val, '1-r', tag=False)
        deftex = r'\sum_{r\in %s} %s %s'%(Gtex,chitexr,psitex1r)
        return r"\( \displaystyle J(%s,%s) = %s = %s.\)" % (chitex, psitex, deftex, latex(jacobi_sum))

    def kloosterman_sum(self, arg):
        a, b = map(int, arg.split(','))
        modulus, number = self.modulus, self.number
        if modulus == 1:
            # there is a bug in sage for modulus = 1
            return r"""
            \( \displaystyle K(%s,%s,\chi_{1}(1,&middot;))
            = \sum_{r \in \mathbb{Z}/\mathbb{Z}}
                 \chi_{1}(1,r) 1^{%s r + %s r^{-1}}
            = 1 \)
            """ % (a, b, a, b)
        chi = self.chi.sage_character()
        k = chi.kloosterman_sum_numerical(100, a, b)
        real = round(k.real(), 5)
        imag = round(k.imag(), 5)
        if imag == 0:
            k = str(real)
        elif real == 0:
            k = str(imag) + "i"
        else:
            k = latex(k)
        return r"""
        \( \displaystyle K(%s,%s,\chi_{%s}(%s,&middot;))
        = \sum_{r \in \mathbb{Z}/%s\mathbb{Z}}
             \chi_{%s}(%s,r) e\left(\frac{%s r + %s r^{-1}}{%s}\right)
        = %s. \)""" % (a, b, modulus, number, modulus, modulus, number, a, b, modulus, k)

class WebHeckeCharacter(WebChar, WebHecke):

    def _compute(self):
        WebHecke._compute(self)
 
        self.number = self.label2number(self.numlabel)
        assert len(self.number) == self.G.ngens()
        self.chi = chi = HeckeChar(self.H, self.number)

        self.order = chi.order()
        self.zetaorder = 0 # FIXME H.zeta_order()
        self.parity = None

    @property
    def codeinit(self):
        kpol = self.k.polynomial()
        return [('sage', '\n'.join(['k.<a> = NumberField(%s)'%kpol,
                          'm = k.ideal(%s)'%self.modulus,
                          'G = RayClassGroup(k,m)',
                          'H = G.dual_group()',
                          'chi = H(%s)'%self.number])),
                ('pari',  '\n'.join(['k=bnfinit(%s)'%kpol,
                           'G=bnrinit(k,m,1)',
                           'chi = %s'%self.number] )) ]

    @property
    def title(self):
      return r"Hecke Character: %s modulo %s" % (self.texname, self.modulus)
    
    @property
    def codecond(self):
        return [('sage', 'chi.conductor()'),
                ('pari', 'bnrconductorofchar(G,chi)')]

    @property
    def inducing(self):
        #return lmfdb_hecke2tex(self.conductor(),self.indlabel())
        return None

    @property
    def indlabel(self):
        #return chi.primitive_character().number()
        return None

    @property
    def generators(self):
        return self.textuple( map(self.group2tex, self.G.gen_ideals() ), tag=False )

    @property
    def genvalues(self):
        logvals = self.chi.logvalues_on_gens()
        return self.textuple( map(self.texlogvalue, logvals))

    @property
    def galoisorbit(self):
        prim = self.isprimitive
        return  [ self._char_desc(c, prim=prim) for c in self.chi.galois_orbit() ]

def next_dirichlet_char(m, n, onlyprimitive=False):
    """ we know that the characters
        chi_m(1,.) and chi_m(m-1,.)
        always exist for m>1.
        They are extremal for a given m.
    """
    if onlyprimitive:
        return next_primitive_char(m, n)
    if m == 1:
        return 2, 1
    if n == m - 1:
        return m + 1, 1
    for k in xrange(n + 1, m):
        if gcd(m, k) == 1:
            return m, k
    raise Exception("next_char")

def prev_dirichlet_char(m, n, onlyprimitive=False):
    """ Assume m>1 """
    if onlyprimitive:
        return prev_primitive_char(m, n)
    if n == 1:
        m, n = m - 1, m
    if m <= 2:
        return m, 1  # important : 2,2 is not a character
    for k in xrange(n - 1, 0, -1):
        if gcd(m, k) == 1:
            return m, k
    raise Exception("next_char")

def prev_dirichlet_primitive_char(m, n):
    if m <= 3:
        return 1, 1
    if n > 2:
        Gm = DirichletGroup_conrey(m)
    while True:
        n -= 1
        if n == 1:  # (m,1) is never primitive for m>1
            m, n = m - 1, m - 1
            Gm = DirichletGroup_conrey(m)
        if m <= 2:
            return 1, 1
        if gcd(m, n) != 1:
            continue
        # we have a character, test if it is primitive
        chi = Gm[n]
        if chi.is_primitive():
            return m, n

def next_dirichlet_primitive_char(m, n):
    if m < 3:
        return 3, 2
    if n < m - 1:
        Gm = DirichletGroup_conrey(m)
    while 1:
        n += 1
        if n == m:
            m, n = m + 1, 2
            Gm = DirichletGroup_conrey(m)
        if gcd(m, n) != 1:
            continue
        # we have a character, test if it is primitive
        chi = Gm[n]
        if chi.is_primitive():
            return m, n

class WebHeckeGroup(WebCharGroup, WebHecke):

    def _compute(self):
        WebHecke._compute(self)
        self.order = self.G.order()
        self._fill_contents()
        self.credit = 'Pari, Sage'
        self.codelangs = ('pari', 'sage')
 
    @property
    def codeinit(self):
        kpol = self.k.polynomial()
        return [('sage', '\n'.join(['k.<a> = NumberField(%s)'%kpol,
                          'm = k.ideal(%s)'%self.modulus,
                          'G = RayClassGroup(k,m)',
                          'H = G.dual_group()' ])),
                ('pari',  '\n'.join(['k=bnfinit(%s)'%kpol,
                           'G=bnrinit(k,m,1)']) )
                ]

    @property
    def title(self):
        return "Group of Hecke characters modulo %s"%(self.modulus)

    @property
    def nf_pol(self):
        #return self.nf.web_poly()
        return self.k.polynomial()._latex_()

    @property
    def generators(self):
        return self.textuple(map(self.group2tex, self.G.gen_ideals()), tag=False)

    @property
    def codegen(self):
        return [('sage','G.gen_ideals()'), ('pari','G.gen')]

    @property
    def groupelts(self):
        print self.Gelts
        print [ self.group2tex(self.G.exp(e)) for e in self.Gelts ]
        return [ self.group2tex(self.G.exp(e)) for e in self.Gelts ]


#############################################################################
###
###    OLD MATERIAL
###
#############################################################################

class WebCharacter:
    """
    Class for presenting a Character on a web page
    """
    def __init__(self, dict):
        self.type = dict['type']
        # self.texname = "\\chi"  # default name.  will be set later, for most L-functions
        self.citation = ''
        self.credit = ''
        if self.type == 'dirichlet':
            self.modulus = int(dict['modulus'])
            self.number = int(dict['number'])
            self.dirichletcharacter()
            self._set_properties()
        elif self.type == 'hecke':
            # need Sage number field... easier way ?
            k = WebNumberField(dict['number_field']).K()
            self.number_field = k
            self.modulus = lmfdb_label2ideal(k, dict['modulus'])
            self.number = lmfdb_label2hecke(dict['number'])
            self.heckecharacter()
            self._set_properties()

    def _set_properties(self):
        conductor = self.conductor
        primitive = self.primitive
        if primitive == "True":
            self.prim = "Yes"
        else:
            self.prim = "No"
        if self.order <= 2:
            self.real = "Yes"
        else:
            self.real = "No"
        order = str(self.order)
        self.properties = [("Conductor", [conductor]),
                           ( "Order", [order]),
                           ("Parity", [self.parity]),
                           ("Real", [self.real]),
                           ("Primitive", [self.prim])]
        
    def dirichletcharacter(self):

        #######################################################################################
        ##  Conrey's naming convention for Dirichlet Characters
        #######################################################################################

        G = DirichletGroup_conrey(self.modulus)
        G_sage = G.standard_dirichlet_group()
        self.level = self.modulus
        if self.modulus == 1 or self.number % self.modulus != 0:
            chi = G[self.number]
            chi_sage = chi.sage_character()
            self.chi_sage = chi_sage
            self.zetaorder = G_sage.zeta_order()
            # if len(chi_sage.values_on_gens()) == 1:
            ###    self.genvaluestex = latex(chi_sage.values_on_gens()[0])
            # else:
            ###    self.genvaluestex = latex(chi_sage.values_on_gens())
            # chizero = G_sage[0]
            self.char = str(chi)
            if chi.is_primitive():
                self.primitive = "True"
            else:
                self.primitive = "False"
            self.conductor = chi.conductor()
            self.order = chi.multiplicative_order()
            self.galoisorbit = [ power_mod(self.number, k, self.modulus) for k in xrange(1, self.order) if gcd(k, self.order) == 1 ]
            self.vals = chi.values()
            self.logvals = log_value(self.modulus, self.number)
            # self.logvals = map(chi.logvalue, range(1,self.modulus+1))
            # self.logvals = [latex_char_logvalue(k,True) for k in self.logvals]
            Gunits = G_sage.unit_gens()
            if self.modulus == 2:
                Gunits = [1]
            self.unitgens = latex_tuple(map(str, Gunits))
            self.genvalues = chi_sage.values_on_gens()  # what is the use ?
            self.genlogvalues = [chi.logvalue(k) for k in Gunits]
            self.genvaluestex = latex_tuple(map(latex_char_logvalue, self.genlogvalues))
            self.bound = 5 * 1024
            if chi.is_even():
                self.parity = 'Even'
            else:
                self.parity = 'Odd'
            if self.primitive == "False":
                self.inducedchar = chi.primitive_character()
                self.inducedchar_isprim = self.inducedchar.is_primitive()
                self.inducedchar_modulus = self.inducedchar.modulus()
                self.inducedchar_conductor = self.inducedchar.conductor()
                F = DirichletGroup_conrey(self.inducedchar_modulus)
                if self.number == 1:
                    self.inducedchar_number = 1
                else:
                    for chi in F:
                        j = chi.number()
                        if chi == self.inducedchar:
                            self.inducedchar_number = j
                            break
                self.inducedchar_tex = r"\(\chi_{%s}(%s,\cdot)\)" % (
                    self.inducedchar_modulus, self.inducedchar_number)
       # if self.primitive == 'True':
       #     self.primtf = True
       # else:
       #     self.primtf = False
            # Set data for related number fields
            order2 = int(self.order)
            if order2 % 4 == 2:
                order2 = order2 / 2
            self.valuefield = r'\(\mathbb{Q}(\zeta_{%d})\)' % order2
            if order2 == 1:
                self.valuefield = r'\(\mathbb{Q}\)'
            if order2 == 4:
                self.valuefield = r'\(\mathbb{Q}(i)\)'
            valuewnf = WebNumberField.from_cyclo(order2)
            if not valuewnf.is_null():
                self.valuefield_label = valuewnf.label
            else:
                self.valuefield_label = ''
            self.texname = r'\chi_{%d}(%d, \cdot)' % (self.modulus, self.number)
            self.kername = r'\(\mathbb{Q}(\zeta_{%d})^{\ker %s}\)' % (self.modulus, self.texname)

            if self.order < 16:
                pol = str(gp.galoissubcyclo(self.modulus, self.chi_sage.kernel()))
                sagepol = PolynomialRing(QQ, 'x')(pol)
                R = sagepol.parent()
                nf_pol = R(pari(sagepol).polredabs())
                self.nf_pol = "\( %s \)" % latex(nf_pol)
                wnf = WebNumberField.from_coeffs([int(c) for c in nf_pol.coeffs()])
                if wnf.is_null():
                    self.nf_friend = ''
                else:
                    self.nf_friend = '/NumberField/' + str(wnf.label)
                    self.nf_label = wnf.label
            else:
                self.nf_pol = ''
                self.nf_friend = ''

            if self.order == 2:
                if self.conductor % 2 == 1:
                    self.kronsymbol = r"\begin{equation} \chi_{%s}(a) = " % (self.number)
                    self.kronsymbol += r"\left(\frac{a}{%s}\right)" % (self.conductor)
                    self.kronsymbol += r"\end{equation}"
                else:
                    if chi.is_even():
                        self.kronsymbol = r"\begin{equation}  \chi_{%s}(a) = " % (self.number)
                        self.kronsymbol += r"\left(\frac{a}{%s}\right)" % (self.conductor)
                        self.kronsymbol += r"\end{equation}"
                    else:
                        self.kronsymbol = r"\begin{equation}  \chi_{%s}(a) = " % (self.number)
                        self.kronsymbol += r"\left(\frac{a}{%s}\right)" % (self.conductor)
                        self.kronsymbol += r"\end{equation}"

        self.credit = "Sage"
        self.title = r"Dirichlet Character: \(\chi_{%s}(%s,\cdot)\)" % (self.modulus, self.number)

        return chi

    def heckecharacter(self):

        G = RayClassGroup(self.number_field, self.modulus)
        H = G.dual_group()
        assert len(self.number) == G.ngens()
        chi = HeckeChar(H,self.number)

        self.order = chi.order()
        self.zetaorder = 0 # FIXME H.zeta_order()

        self.unitgens = latex_tuple(map(lmfdb_ideal2tex, G.gen_ideals()))
        self.genvaluestex = latex_tuple(map(latex_char_logvalue, chi.logvalues_on_gens()))


        # not relevant over ideals
        #self.parity = ('Odd', 'Even')[chi.is_even()]
        self.parity = 'None'

        self.conductor = lmfdb_ideal2tex(chi.conductor())

        self.primitive = str(chi.is_primitive())

        self.texname = lmfdb_hecke2tex(chi)
        
        order2 = int(self.order)
        if order2 % 4 == 2:
            order2 = order2 / 2
        self.valuefield = r'\(\mathbb{Q}(\zeta_{%d})\)' % order2
        if order2 == 1:
            self.valuefield = r'\(\mathbb{Q}\)'
        if order2 == 4:
            self.valuefield = r'\(\mathbb{Q}(i)\)'
        valuewnf = WebNumberField.from_cyclo(order2)
        if not valuewnf.is_null():
            self.valuefield_label = valuewnf.label
        else:
            self.valuefield_label = ''
        
        mod_tex = lmfdb_ideal2tex(self.modulus)
        mod_label = lmfdb_ideal2label(self.modulus)
        self.galoisorbit = [ ( mod_label, lmfdb_hecke2label(c), lmfdb_hecke2tex(c) ) for c in chi.galois_orbit() ]

        self.credit = "Pari, Sage"
        self.title = r"Hecke Character: %s modulo \(%s\)" % (self.texname, mod_tex)

        return chi

