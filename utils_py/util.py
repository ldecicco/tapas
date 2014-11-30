#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# Copyright (c) Vittorio Palmisano <vpalmisano@gmail.com>
#
import sys
import os

### debug
DEBUG_LEVEL = int(os.environ.get('DEBUG', -1))

def debug(level, s, *args):
    if DEBUG_LEVEL >= level or level == 0:
        #print '%s [%s]' %(strftime('%Y-%m-%d-%H.%M.%S'), __name__),
        print s %args

### get HTTP page
from twisted.web import client

def getPage(url, contextFactory=None, *args, **kwargs):
    """Download a web page as a string.

    Download a page. Return a HTTPClientFactory

    See HTTPClientFactory to see what extra args can be passed.
    """
    #scheme, host, port, path = client._parse(url)
    scheme, _ = url.split('://', 1)
    
    host_port, path = _.split('/', 1)
    try:
        host, port = host_port.split(':')
        port = int(port)
    except Exception:
        host = host_port
        port = 80
    path = '/'+path
    factory = client.HTTPClientFactory(url, *args, **kwargs)
    factory.noisy = False
    if scheme == 'https':
        from twisted.internet import ssl
        if contextFactory is None:
            contextFactory = ssl.ClientContextFactory()
        reactor.connectSSL(host, port, factory, contextFactory)
    else:
        reactor.connectTCP(host, port, factory)
    return factory

### files usage
def files_usage():
    return int(os.popen('lsof -a -p %d | wc -l' %os.getpid()).read())

### mem usage
def memory_usage(size='rss'):
    """memory sizes: rss, rsz, vsz."""
    return int(os.popen('ps -p %d -o %s | tail -1' %
        (os.getpid(), size)).read())

###
from BaseHTTPServer import BaseHTTPRequestHandler
import cgi
from urlparse import parse_qs
from StringIO import StringIO

class HttpRequest(BaseHTTPRequestHandler):
    def __init__(self, request_text):
        self.path = ''
        self.rfile = StringIO(request_text)
        self.raw_requestline = self.rfile.readline()
        self.error_code = self.error_message = None
        self.parse_request()
        self.query = {}
        self.method = request_text[:4].strip().lower()
        if '?' in self.path:
            self.path, _ = self.path.split('?', 2)
            for k,v in parse_qs(_).iteritems():
                if isinstance(v, list):
                    self.query[k] = v[0]
                else:
                    self.query[k] = v

    def send_error(self, code, message):
        self.error_code = code
        self.error_message = message

    def __repr__(self):
        return '<HttpRequest method=%s path=%s query=%s>' %(self.method, self.path, self.query)

    def toDict(self):
        return dict(method=self.method, path=self.path, query=self.query)

###
import gc
import inspect

def dump_garbage():
    # force collection
    gc.collect()
    gc.collect()
    if gc.garbage:
        print "\nGarbage objects:"
    for x in gc.garbage:
        s = str(x)
        if len(s) > 80: 
            s = "%s..." % s[:80]
        print "::", s
        print "        type:", type(x)
        print "   referrers:", len(gc.get_referrers(x))
        try:
            print "    is class:", inspect.isclass(type(x))
            print "      module:", inspect.getmodule(x)
            lines, line_num = inspect.getsourcelines(type(x))
            print "    line num:", line_num
            for l in lines:
                print "        line:", l.rstrip("\n")
        except:
            pass
        print

### logger
from time import time, strftime

class Logger(object):
    def __init__(self, optlist, log_period=0.1, log_prefix='', comment='', 
            log_dir='logs'):
        self.log_fd = None
        self.logfile = ''
        self.logs_dir = get_path(log_dir)
        self.last_log_t = time()
        self.min_log_period = log_period #s
        # init log file
        if not os.path.exists(self.logs_dir):
            os.makedirs(self.logs_dir)
            os.chmod(self.logs_dir, 0777)
            print self.logfile
        if os.environ.get('DEBUG_PREFIX'):
            self.logfile = self.logs_dir+'/%s_%d.log' %(
                    os.environ.get('DEBUG_PREFIX'), id(self))
        if log_prefix:
        #    self.logfile = self.logs_dir+'/%s.log' %log_prefix
            self.logfile = self.logs_dir+'/%s_%s_%d_%d.log' %(log_prefix, 
                    strftime('%Y-%m-%d-%H.%M.%S'), os.getpid(), id(self))
        else:
            self.logfile = self.logs_dir+'/%s_%d_%d.log' %(
                    strftime('%Y-%m-%d-%H.%M.%S'), os.getpid(), id(self))
        self.log_fd = open(self.logfile, 'w')
        os.chmod(self.logfile, 0666)
        # write header
        self.format_string = r'%(now).2f'
        header = '#ts'
        for name, type_, opt in optlist:
            header += ' '+name
            if opt:
                header += ','+opt
            self.format_string += r' %('+name+')'
            if type_ == int:
                self.format_string += r'd'
            elif type_ == float:
                self.format_string += r'.3f'
        self.format_string += '\n'
        self.log_fd.write('%s\n' %header)
        if comment:
            self.log_fd.write('#%s\n' %comment)
        self.log_fd.flush()

    def log_comment(self, comment):
        if not self.log_fd:
            return
        self.log_fd.write('#%s\n' %comment)
        self.log_fd.flush()

    def log(self, logdict):
        now = time()
        if now - self.last_log_t < self.min_log_period:
            return
        self.last_log_t = now
        logdict['now'] = now
        self.log_fd.write(self.format_string %logdict)
        self.log_fd.flush()

def parse_log_data(data):
    d = dict(request='', signals=[], values={})
    t0 = 0
    for line in data.split('\n'):
        if line.startswith('#'):
            if not d['signals']:
                for signal in line[1:].split(' '):
                    s = signal.split(',')
                    signal_dict = dict(name=s[0])
                    for prop in s[1:]:
                        p = prop.split('=')
                        signal_dict[p[0]] = p[1]
                    d['signals'].append(signal_dict)
            elif not d['request']:
                d['request'] = json.loads(line[1:])
        else:
            try:
                vals = map(float, line.split(' '))
            except Exception, e:
                print e
                continue
            if t0 == 0:
                t0 = vals[0]
                d['t0'] = t0
            vals[0] -= t0
            for (s,v) in zip(d['signals'], vals):
                d['values'].setdefault(s['name'], []).append(v)
    return d

### get_path
def get_path(filename):
    if not os.path.isabs(filename):
        _dirname = os.path.dirname(sys.argv[0])
        return os.path.abspath(os.path.join(_dirname, filename))
    else:
        return filename

### options
from twisted.python import usage
import json

def get_options(optParameters):
    class Options(usage.Options):
        pass
    optParameters.insert(0, ('config', 'c', '', 'Configuration file', str))
    Options.optParameters = optParameters
    options = Options()
    try:
        options.parseOptions()
    except Exception, e:
        print '%s: %s' % (sys.argv[0], e)
        print '%s: Try --help for usage details.' % (sys.argv[0])
        sys.exit(1)
    if options['config']:
        debug(2, 'Loading options from: %s', options['config'])
        # get from file
        try:
            if options['config'].endswith('.json'):
                data = open(get_path(options['config'])).read()
                options = json.loads(str(data))
            elif options['config'].endswith('.py'):
                path = os.path.dirname(get_path(options['config']))
                sys.path.insert(0, path)
                options = __import__(options['config'][:-3]).options
        except Exception, e:
            print 'Error loading options:', e
            print 'Using defaults.'
    return options

### RateCalc
import gobject
from time import time
from twisted.internet import reactor
from numpy import numarray

class RateCalc(gobject.GObject):
    __gsignals__ = {
        'update': (
            gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()
        ),
    }

    def __init__(self, period=0.5, alpha=0.5):
        gobject.GObject.__init__(self)
        self.period = period
        self.alpha = alpha
        self.last_t = 0.0
        self.last_data = 0
        self.rate = 0.0
        self.rate_filt = -1
        self.horizon = 5
        self.rate_vec = CircularBuffer(self.horizon)
        self.running = False
        self.calc_iteration_id = None
    
    def __repr__(self):
        return '<RateCalc rate=%(rate).3f period=%(period).3f alpha=%(alpha).3f>' %(
            self.__dict__)

    def start(self):
        #debug(1, "%s start", self)
        self.running = True
        #self.calc_iteration_id = gobject.timeout_add(int(self.period*1000),
        #    self.calc_iteration)
        reactor.callLater(self.period, self.calc_iteration)

    def stop(self):
        self.running = False
        if self.calc_iteration_id:
            gobject.source_remove(self.calc_iteration_id)
            self.calc_iteration_id = None

    def update(self, size):
        self.last_data += size

    def harmonic_mean(self, v):
        '''Computes the harmonic mean of vector v'''
        x = numarray.array(v)
        #debug(DEBUG, "Bwe vect: %s", str(x))
        m =  1.0/(sum(1.0/x)/len(x))
        #debug(DEBUG, "Harmonic mean: %.2f", m)
        return m

    def calc_iteration(self):
        if not self.running or not reactor.running:
            debug(1, '%s exiting', self)
            return False
        if not self.last_t:
            self.last_t = time()
        now = time()
        if now - self.last_t >= self.period:
            self.rate = self.alpha*self.rate + \
                (1.0-self.alpha)*self.last_data/(now - self.last_t)
            self.last_data = 0
            self.last_t = now
            self.rate_vec.add(self.rate)
            #self.rate_filt = self.harmonic_mean(self.rate_vec.getBuffer())
            self.emit('update')
        reactor.callLater(self.period, self.calc_iteration)
        #return True
gobject.type_register(RateCalc)

#CircularBuffer
class CircularBuffer(object):
     
    def __init__(self, length, init_v=None):
        self.length = length
        self._buf = [0] * length
        self._pos = 0
        if init_v and type(init_v) == list and len(init_v) <= self.length:
            self._buf[0:len(init_v)] = init_v
            self._pos = len(init_v)

    def add(self, val):
        self._buf[1:self.length] = self._buf[0:self.length-1]
        self._buf[0] = val
        if self._pos < self.length:
            self._pos += 1
   
    def getBuffer(self):
        return self._buf[0:self._pos]

### SVN
from subprocess import Popen, PIPE
import os
def get_svn_revision():
    if not os.path.exists('.svn'):
        return 0
    '''version = 0
    p = Popen('svn info --xml', shell=True, stdout=PIPE)
    p.wait()
    for line in p.stdout:
        if 'revision="' in line:
            version = line.replace('revision="', '').replace('">', '').strip()
            break
    return int(version)'''
    i = 0
    for line in open('.svn/entries'):
        i += 1
        if i == 4:
            return int(line)

### force close thread
import ctypes
import threading

def _async_raise(tid, excobj):
    # http://code.activestate.com/recipes/496960/
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(excobj))
    if res == 0:
        raise ValueError("nonexistent thread id")
    elif res > 1:
        # """if it returns a number greater than one, you're in trouble, 
        # and you should call it again with exc=NULL to revert the effect"""
        ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, 0)
        raise SystemError("PyThreadState_SetAsyncExc failed")

def kill_threads():
    for tid, tobj in threading._active.items():
        print tid, tobj.getName()
        if tobj.getName() != 'MainThread':
            _async_raise(tid, SystemExit)

### get hz value
import ctypes
import socket
import struct
from subprocess import call

def get_hz():
    try:
        ret = call("cat /lib/modules/`uname -r`/build/.config | grep '^CONFIG_HZ=[0-9]*' | sed s/'CONFIG_HZ='//", shell=True)
        return int(ret)
    except Exception, e:
        print e
        return 250

#HZ = get_hz()

### tcpinfo
class TcpInfo(ctypes.Structure):
    _fields_ = [
        ('tcpi_state', ctypes.c_uint8),
        ('tcpi_ca_state', ctypes.c_uint8),
        ('tcpi_retransmits', ctypes.c_uint8),
        ('tcpi_probes', ctypes.c_uint8),
        ('tcpi_backoff', ctypes.c_uint8),
        ('tcpi_options', ctypes.c_uint8),
        ('tcpi_snd_wscale', ctypes.c_uint8),
        ('tcpi_rcv_wscale', ctypes.c_uint8),

        ('tcpi_rto', ctypes.c_uint32), 
        ('tcpi_ato', ctypes.c_uint32),
        ('tcpi_snd_mss', ctypes.c_uint32),
        ('tcpi_rcv_mss', ctypes.c_uint32),

        ('tcpi_unacked', ctypes.c_uint32), 
        ('tcpi_sacked', ctypes.c_uint32),
        ('tcpi_lost', ctypes.c_uint32),
        ('tcpi_retrans', ctypes.c_uint32),
        ('tcpi_fackets', ctypes.c_uint32),

        # Times
        ('tcpi_last_data_sent', ctypes.c_uint32), 
        ('tcpi_last_ack_sent', ctypes.c_uint32),
        ('tcpi_last_data_recv', ctypes.c_uint32),
        ('tcpi_last_ack_recv', ctypes.c_uint32),

        # Metrics
        ('tcpi_pmtu', ctypes.c_uint32), 
        ('tcpi_rcv_ssthresh', ctypes.c_uint32),
        ('tcpi_rtt', ctypes.c_uint32),
        ('tcpi_rttvar', ctypes.c_uint32),
        ('tcpi_snd_ssthresh', ctypes.c_uint32), 
        ('tcpi_snd_cwnd', ctypes.c_uint32),
        ('tcpi_advmss', ctypes.c_uint32),
        ('tcpi_reordering', ctypes.c_uint32),

        ('tcpi_rcv_rtt', ctypes.c_uint32),
        ('tcpi_rcv_space', ctypes.c_uint32),

        ('tcpi_total_retrans', ctypes.c_uint32),

        #('tcpi_westwood_bwe', ctypes.c_uint32),
    ]

    def __init__(self, sk):
        buf = sk.getsockopt(socket.SOL_TCP, socket.TCP_INFO, ctypes.sizeof(TcpInfo))
        assert len(buf) == ctypes.sizeof(TcpInfo)
        desc = ''
        for name,t in self._fields_:
            if t == ctypes.c_uint8:
                desc += 'B'
            elif t == ctypes.c_uint32:
                desc += 'I'
        self.values = struct.unpack(desc, buf)
        for i in range(len(self._fields_)):
            setattr(self, self._fields_[i][0], self.values[i])

    def __str__(self):
        return '<TcpInfo (cwnd: %d (%d B) rtt: %.2f)>' %(
            self.tcpi_snd_cwnd, 
            self.tcpi_pmtu*self.tcpi_snd_cwnd,
            self.tcpi_rtt*1e-6, 
            )

    def get_cwnd(self):
        return self.tcpi_pmtu*self.tcpi_snd_cwnd
    
    def get_rtt(self):
        return self.tcpi_rtt*1.0e-6

    def props(self):
        return ' '.join([n[0] for n in self._fields_])

# format bytes
def format_bytes(v):
    if not v:
        return '0'
    if v < 1024:
        return '%d B' %v
    elif v < 1024**2:
        return '%.2f KB' %(v/1024.)
    elif v < 1024**3:
        return '%.2f MB' %(v/(1024.**2))
    else:
        return '%.2f GB' %(v/(1024.**3))

# console colors
NORMAL = '\033[m'
WHITE_BOLD = '\033[1m'

def bold(*s):
    return '%s%s%s' %(WHITE_BOLD, ' '.join([str(w) for w in s]), NORMAL)

# logging setup
from twisted.python import log
from twisted.python.logfile import DailyLogFile
    
def init_logging(logdir, logname):
    if DEBUG_LEVEL > 0:
        log.startLogging(sys.stdout)
    if not os.path.exists(logdir):
        os.makedirs(logdir)
    logfile = get_path(os.path.join(logdir, logname))
    log.startLogging(DailyLogFile.fromFullPath(logfile))

### process stats
import psutil

class ProcessStats(object):
    def __init__(self, directory=None, calc_temp=False):
        self_last_cpu_u, self._last_cpu_s, self._last_t  = 0, 0, 0
        self._directory = directory
        self._calc_temp = calc_temp
        self.process = psutil.Process(os.getpid())
    
    def stop(self):
        self.process = None

    def getStats(self):
        """
        Returns a dictionary containing the server stats and cpu/memory utilization
        """
        # cpu
        if not self.process:
            return {}
        t = os.times()
        cpu_user, cpu_system = 0, 0
        delta_t = t[-1]-self._last_t
        if self._last_t and delta_t > 0:
            cpu_user = (t[0]-self._last_cpu_u)*100./delta_t
            cpu_system = (t[1]-self._last_cpu_s)*100./delta_t
        self._last_cpu_u, self._last_cpu_s, self._last_t = t[0], t[1], t[-1]
        # memory
        m = self.process.get_memory_info()
        d = dict(
            cpu_percent=cpu_user+cpu_system,
            cpu_user_percent=cpu_user,
            cpu_system_percent=cpu_system,
            memory_percent=self.process.get_memory_percent(),
            memory_rss=m.rss, 
            memory_vms=m.vms,
            #open_files=self.process.get_num_fds(),
            #open_files_max=self.process.get_rlimit(psutil.RLIMIT_NOFILE)[1],
            threads=self.process.get_num_threads(),
            connections=self.process.get_connections().__len__(),
        )
        # temp
        if self._calc_temp:
            try:
                d['temp'] = Popen(['/usr/bin/acpi', '-t'], stdout=PIPE).communicate()[0]
            except Exception:
                pass
        # disk
        if self._directory:
            usage = psutil.disk_usage(self._directory)
            d['disk_usage'] = usage.percent
            d['disk_used'] = usage.used
        return d

from twisted.web.client import HTTPClientFactory
from twisted.internet import ssl
from urllib import urlencode

def send_json(url, **kw):
    qurl =url+'?'+urlencode(kw.get('postdata', {}))
    # debug(0,'URLSTATS: %s',qurl)
    factory = HTTPClientFactory(str(qurl))
    factory.noisy = False
    if url.startswith('http://'):
        reactor.connectTCP(factory.host, factory.port, factory)
    elif url.startswith('https://'):
        reactor.connectSSL(factory.host, factory.port, factory, 
            ssl.ClientContextFactory())
    else:
        raise Exception('Url error: %s' %url)
    return factory

def makeJsonUrl(url,**kw):
    return str(url+'?'+urlencode(kw.get('data', {})))

### debug shell
def start_debug_shell(d=None, port=9000):
    # Add a manhole shell
    import twisted.manhole.telnet
    f = twisted.manhole.telnet.ShellFactory()
    f.namespace['_'] = d
    try:
        import objgraph
        f.namespace['g'] = objgraph.show_growth
    except Exception:
        pass
    return reactor.listenTCP(port, f, interface='127.0.0.1')
