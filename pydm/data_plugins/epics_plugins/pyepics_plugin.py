import epics
import numpy as np
from ..plugin import PyDMPlugin, PyDMConnection
from ...PyQt.QtCore import pyqtSlot, Qt

int_types = set((epics.dbr.INT, epics.dbr.CTRL_INT, epics.dbr.TIME_INT, 
                 epics.dbr.ENUM, epics.dbr.CTRL_ENUM, epics.dbr.TIME_ENUM, 
                 epics.dbr.TIME_LONG, epics.dbr.LONG, epics.dbr.CTRL_LONG, 
                 epics.dbr.CHAR, epics.dbr.TIME_CHAR, epics.dbr.CTRL_CHAR, 
                 epics.dbr.TIME_SHORT, epics.dbr.CTRL_SHORT))

float_types = set((epics.dbr.CTRL_FLOAT, epics.dbr.FLOAT, epics.dbr.TIME_FLOAT, 
                   epics.dbr.CTRL_DOUBLE, epics.dbr.DOUBLE, epics.dbr.TIME_DOUBLE))

class Connection(PyDMConnection):
    def __init__(self, channel, pv, parent=None):
        super(Connection, self).__init__(channel, pv, parent)
        self.pv = epics.PV(pv, connection_callback=self.send_connection_state, form='ctrl', auto_monitor=True, access_callback=self.send_access_state)
        self.pv.add_callback(self.send_new_value, with_ctrlvars=True)
        self.add_listener(channel)

        self._severity = None
        self._precision = None
        self._enum_strs = None
        self._unit = None
        self._upper_ctrl_limit = None
        self._lower_ctrl_limit = None
  
    def clear_cache(self):
        self._severity = None
        self._precision = None
        self._enum_strs = None
        self._unit = None
        self._upper_ctrl_limit = None
        self._lower_ctrl_limit = None

    def send_new_value(self, value=None, char_value=None, count=None, ftype=None, *args, **kws):
        self.update_ctrl_vars(**kws)
        if value is not None:
            if isinstance(value, np.ndarray):
                self.new_value_signal[np.ndarray].emit(value)
            else:
                if ftype in int_types:
                    self.new_value_signal[int].emit(int(value))
                elif ftype in float_types:
                    self.new_value_signal[float].emit(float(value))
                else:
                    self.new_value_signal[str].emit(char_value)
    
    def update_ctrl_vars(self, units=None, enum_strs=None, severity=None, upper_ctrl_limit=None, lower_ctrl_limit=None, precision=None, *args, **kws):
        if severity is not None and self._severity != severity:
            self._severity = severity
            self.new_severity_signal.emit(int(severity))
        if precision is not None and self._precision != precision:
            self._precision = precision
            self.prec_signal.emit(precision)
        if enum_strs is not None and self._enum_strs != enum_strs:
            self._enum_strs = enum_strs
            try:
                enum_strs = tuple(b.decode(encoding='ascii') for b in enum_strs)
            except AttributeError:
                pass
            self.enum_strings_signal.emit(enum_strs)
        if units is not None and len(units) > 0 and self._unit != units:
            if type(units) == bytes:
                units = units.decode()
            self._unit = units
            self.unit_signal.emit(units)
        if upper_ctrl_limit is not None and self._upper_ctrl_limit != upper_ctrl_limit:
            self._upper_ctrl_limit = upper_ctrl_limit
            self.upper_ctrl_limit_signal.emit(upper_ctrl_limit)    
        if lower_ctrl_limit is not None and self._lower_ctrl_limit != lower_ctrl_limit:
            self._lower_ctrl_limit = lower_ctrl_limit
            self.lower_ctrl_limit_signal.emit(lower_ctrl_limit)    

    def send_access_state(self, read_access, write_access, *args, **kws):
        if write_access is not None:
            self.write_access_signal.emit(write_access)
    
    def reload_access_state(self):
        read_access = epics.ca.read_access(self.pv.chid)
        write_access = epics.ca.write_access(self.pv.chid)
        self.send_access_state(read_access, write_access)

    def send_connection_state(self, conn=None, *args, **kws):
        self.connection_state_signal.emit(conn)
        if conn:
            self.clear_cache()
            if hasattr(self, 'pv'):
                self.reload_access_state()
                self.pv.run_callbacks()

    @pyqtSlot(int)
    @pyqtSlot(float)
    @pyqtSlot(str)
    @pyqtSlot(np.ndarray)
    def put_value(self, new_val):
        if self.pv.write_access:
            self.pv.put(new_val)
    
    def add_listener(self, channel):
        super(Connection, self).add_listener(channel)
        # If we are adding a listener to an already existing PV, we need to
        # manually send the signals indicating that the PV is connected, what the latest value is, etc.
        if epics.ca.isConnected(self.pv.chid):
            self.send_connection_state(conn=True)
            self.pv.run_callbacks()
        # If the channel is used for writing to PVs, hook it up to the 'put' methods.  
        if channel.value_signal is not None:
            try:
                channel.value_signal[str].connect(self.put_value, Qt.QueuedConnection)
            except KeyError:
                pass
            try:
                channel.value_signal[int].connect(self.put_value, Qt.QueuedConnection)
            except KeyError:
                pass
            try:
                channel.value_signal[float].connect(self.put_value, Qt.QueuedConnection)
            except KeyError:
                pass
            try:
                channel.value_signal[np.ndarray].connect(self.put_value, Qt.QueuedConnection)
            except KeyError:
                pass

    def close(self):
        self.pv.disconnect()

class PyEPICSPlugin(PyDMPlugin):
    # NOTE: protocol is intentionally "None" to keep this plugin from getting directly imported.
    # If this plugin is chosen as the One True EPICS Plugin in epics_plugin.py, the protocol will
    # be properly set before it is used.
    protocol = None
    connection_class = Connection
