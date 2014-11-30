#!/usr/bin/env python
# -*- encoding: utf-8 -*-

def gst_init():
    from twisted.internet import gireactor as reactor
    reactor.install()
    import gi
    gi.require_version('Gst', '1.0')
    from gi.repository import GObject, Gst
    GObject.threads_init()
    Gst.init(None)

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject

gst_buffer_new_allocate = Gst.Buffer.new_allocate
def gst_buffer(data):
    buf = gst_buffer_new_allocate(None, len(data), None)
    buf.fill(0, data)
    return buf

def gst_buffer_is_keyframe(buf):
    return not (buf.mini_object.flags & Gst.BufferFlags.DELTA_UNIT)

def gst_pipeline_recurse(pipeline):
    if not pipeline:
        raise StopIteration
    it = pipeline.iterate_recurse()
    state, e = it.next()
    while e:
        yield e
        state, e = it.next()

def gst_register_plugin(klass, name):
    element_class = GObject.type_class_peek(klass.__gtype__)
    element_class.__class__ = Gst.ElementClass
    element_class.set_metadata(*klass.__gstdetails__)
    for pad_template in klass.__gsttemplates__:
        element_class.add_pad_template(pad_template)
    klass.register(None, name, Gst.Rank.NONE, klass.__gtype__)

def gst_pad_add_probe(pipeline, element_name, pad_name):
    pad = pipeline.get_by_name(element_name).get_static_pad(pad_name)
    def _on_buffer_in(pad, info, data):
        buf = info.get_buffer()
        print(element_name, pad_name, pad, buf.pts*1e-9, buf.get_size(), pad.get_current_caps())
        return Gst.PadProbeReturn.OK
    return pad.add_probe(Gst.PadProbeType.BUFFER, _on_buffer_in, None)

def gst_get_queues(pipeline, bytes_min=0):
    '''
    Returns pipeline's queues in the format:
        (queue_name, buffers time(seconds), bytes)
    '''
    for e in gst_pipeline_recurse(pipeline):
        if e.get_factory().get_name() in ('queue', 'matroskaqueue'):
            name = e.get_property('name')
            bufs = e.get_property('current-level-buffers')
            t = e.get_property('current-level-time')*1e-9
            b = e.get_property('current-level-bytes')
            if b > bytes_min:
                yield name, bufs, t, b
    raise StopIteration

if __name__ == '__main__':
    pass
