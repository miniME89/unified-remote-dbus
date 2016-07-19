import sys
import glib
import gobject
import dbus
import json
import time
import threading
from dbus.mainloop.glib import DBusGMainLoop

DBUS_PATH = '/org/freedesktop/DBus'
DBUS_INTERFACE = 'org.freedesktop.DBus'
PROPERTIES_INTERFACE = 'org.freedesktop.DBus.Properties'

MPRIS_PATH = '/org/mpris/MediaPlayer2'
MPRIS_INTERFACE = 'org.mpris.MediaPlayer2'
MPRIS_PLAYER_INTERFACE = 'org.mpris.MediaPlayer2.Player'

def eprint(message):
    print >>sys.stderr, message

#dbus.Double is not converted to a proper number type with json.dumps.. lets fix that
def fixDbusTypes(data):
    if isinstance(data, dbus.Double):
        return float(data)
    elif isinstance(data, dict):
        for k, v in data.items():
            data[k] = fixDbusTypes(v)
    elif isinstance(data, list):
        for k, v in enumerate(data):
            data[k] = fixDbusTypes(v)

    return data

class MediaPlayer:
    def __init__(self):
        self.name = None
        self.playerInterface = None
        self.propertiesInterface = None

        self._properties = {
            'PlaybackStatus': None,
            'LoopStatus': None,
            'Rate': 0,
            'Shuffle': False,
            'Metadata': None,
            'Volume': 0,
            'Position': 0,
            'MinimumRate': 0,
            'MaximumRate': 0,
            'CanGoNext': False,
            'CanGoPrevious': False,
            'CanPlay': False,
            'CanPause': False,
            'CanSeek': False,
            'CanControl': False
        }

        self._sync = {
            'time': 0,
            'position': 0
        }

        #setup dbus
        self._loop = gobject.MainLoop()
        self._bus = dbus.SessionBus(mainloop=DBusGMainLoop())
        self._bus.add_signal_receiver(self._nameOwnerChanged, signal_name='NameOwnerChanged', dbus_interface=DBUS_INTERFACE, path=DBUS_PATH)

        self._updatePosition()

    def _connect(self, name):
        self._disconnect()

        self.name = name

        proxy = self._bus.get_object(self.name, MPRIS_PATH)
        self.playerInterface = dbus.Interface(proxy, dbus_interface=MPRIS_PLAYER_INTERFACE)
        self.propertiesInterface = dbus.Interface(proxy, dbus_interface=PROPERTIES_INTERFACE)

        self._bus.add_signal_receiver(self._propertiesChanged, signal_name='PropertiesChanged', dbus_interface=PROPERTIES_INTERFACE, path=MPRIS_PATH, bus_name=self.name)
        self._bus.add_signal_receiver(self._seekedSignal, signal_name='Seeked', dbus_interface=MPRIS_PLAYER_INTERFACE, path=MPRIS_PATH, bus_name=self.name)

        self._properties['PlaybackStatus'] = self.propertiesInterface.Get(MPRIS_PLAYER_INTERFACE, 'PlaybackStatus')
        self._properties['LoopStatus'] = self.propertiesInterface.Get(MPRIS_PLAYER_INTERFACE, 'LoopStatus')
        self._properties['Rate'] = self.propertiesInterface.Get(MPRIS_PLAYER_INTERFACE, 'Rate')
        self._properties['Shuffle'] = self.propertiesInterface.Get(MPRIS_PLAYER_INTERFACE, 'Shuffle')
        self._properties['Metadata'] = self.propertiesInterface.Get(MPRIS_PLAYER_INTERFACE, 'Metadata')
        self._properties['Volume'] = self.propertiesInterface.Get(MPRIS_PLAYER_INTERFACE, 'Volume')
        self._properties['MinimumRate'] = self.propertiesInterface.Get(MPRIS_PLAYER_INTERFACE, 'MinimumRate')
        self._properties['MaximumRate'] = self.propertiesInterface.Get(MPRIS_PLAYER_INTERFACE, 'MaximumRate')
        self._properties['CanGoNext'] = self.propertiesInterface.Get(MPRIS_PLAYER_INTERFACE, 'CanGoNext')
        self._properties['CanGoPrevious'] = self.propertiesInterface.Get(MPRIS_PLAYER_INTERFACE, 'CanGoPrevious')
        self._properties['CanPlay'] = self.propertiesInterface.Get(MPRIS_PLAYER_INTERFACE, 'CanPlay')
        self._properties['CanPause'] = self.propertiesInterface.Get(MPRIS_PLAYER_INTERFACE, 'CanPause')
        self._properties['CanSeek'] = self.propertiesInterface.Get(MPRIS_PLAYER_INTERFACE, 'CanSeek')
        self._properties['CanControl'] = self.propertiesInterface.Get(MPRIS_PLAYER_INTERFACE, 'CanControl')

        self._syncPosition()

    def _disconnect(self):
        if self.isConnected():
            self._bus.remove_signal_receiver(self._propertiesChanged, signal_name='PropertiesChanged', dbus_interface=PROPERTIES_INTERFACE, path=MPRIS_PATH, bus_name=self.name)
            self._bus.remove_signal_receiver(self._seekedSignal, signal_name='Seeked', dbus_interface=MPRIS_PLAYER_INTERFACE, path=MPRIS_PATH, bus_name=self.name)

            self.name = None
            self.playerInterface = None
            self.propertiesInterface = None

            self._properties['PlaybackStatus'] = None
            self._properties['LoopStatus'] = None
            self._properties['Rate'] = 0
            self._properties['Shuffle'] = False
            self._properties['Metadata'] = None
            self._properties['Volume'] = 0
            self._properties['Position'] = 0
            self._properties['MinimumRate'] = 0
            self._properties['MaximumRate'] = 0
            self._properties['CanGoNext'] = False
            self._properties['CanGoPrevious'] = False
            self._properties['CanPlay'] = False
            self._properties['CanPause'] = False
            self._properties['CanSeek'] = False
            self._properties['CanControl'] = False

    def _findPlayer(self):
        for name in self._bus.list_names():
            if MPRIS_INTERFACE in name:
                self._connect(name)
                return

    def _syncPosition(self):
        self._properties['Position'] = self.propertiesInterface.Get(MPRIS_PLAYER_INTERFACE, 'Position')
        self._sync['time'] = time.time()
        self._sync['position'] = self._properties['Position']

    def _updatePosition(self):
        if self._properties['PlaybackStatus'] == 'Playing':
            currentTime = time.time()
            elapsed = currentTime - self._sync['time']

            self._properties['Position'] = self._sync['position'] + int(elapsed * self._properties['Rate'] * 1000000)

        try:
            self._updatePositionTimer = threading.Timer(0.5, self._updatePosition)
            self._updatePositionTimer.start()
        except:
            self.quit()

    def _nameOwnerChanged(self, name, new, old):
        if MPRIS_INTERFACE in name:
            #current player closed
            if old == '' and self.name == name:
                self._disconnect()
                self._findPlayer()
            #new player opened
            elif old != '':
                self._connect(name)

    def _propertiesChanged(self, name, properties, invalidProperties):
        for name in properties:
            fixedName = name[0].capitalize() + name[1:]
            self._properties[fixedName] = properties[name]

            if fixedName == 'PlaybackStatus' or fixedName == 'Rate':
                self._syncPosition()

    def _seekedSignal(self, pos):
        self._syncPosition()

    def _processStdin(self, fd, condition):
        line = fd.readline()

        #EOF
        if not line:
            try:
                time.sleep(0.1)
                return True
            except:
                self.quit()
                return False

        if line != "\n":
            split = line.strip().split(',')
            name = split[0]
            args = split[1:]

            try:
                for i, arg in enumerate(args):
                    args[i] = eval(arg)

                method = getattr(self, name)
                result = method(*args)
                if result != None:
                    str = json.dumps(fixDbusTypes(result))
                    print(str)
                    eprint("")
                else:
                    print("")
                    eprint("")
            except Exception as e:
                print("")
                eprint(e)

            sys.stdout.flush()

        return True

    def _processClose(self, fd, condition):
        self.quit()

        return False

    def run(self):
        self._findPlayer()

        glib.io_add_watch(sys.stdin, glib.IO_IN, self._processStdin)
        glib.io_add_watch(sys.stdin, glib.IO_HUP, self._processClose)

        try:
            self._loop.run()
        except KeyboardInterrupt:
            pass

    def quit(self):
        try:
            self._updatePositionTimer.cancel()
        except:
            pass
        self._loop.quit()

    def isConnected(self):
        return self.playerInterface != None

    def getProperties(self):
        return self._properties

    def getProperty(self, name):
        return self._properties[name]

    def setProperty(self, name, value):
        if (name in self._properties):
            self.propertiesInterface.Set(MPRIS_PLAYER_INTERFACE, name, value)
            self._properties[name] = self.propertiesInterface.Get(MPRIS_PLAYER_INTERFACE, name)

    def Next(self):
        if (self.isConnected):
            self.playerInterface.Next()

    def Previous(self):
        if (self.isConnected):
            self.playerInterface.Previous()

    def Pause(self):
        if (self.isConnected):
            self.playerInterface.Pause()

    def PlayPause(self):
        if (self.isConnected):
            self.playerInterface.PlayPause()

    def Stop(self):
        if (self.isConnected):
            self.playerInterface.Stop()

    def Play(self):
        if (self.isConnected):
            self.playerInterface.Play()

    def Seek(self, pos):
        if (self.isConnected):
            self.playerInterface.Seek(pos)

    def SetPosition(self, trackId, pos):
        if (self.isConnected):
            self.playerInterface.SetPosition(trackId, pos)

    def OpenUri(self, uri):
        if (self.isConnected):
            self.playerInterface.OpenUri(uri)

def main():
    mediaPlayer = MediaPlayer()
    mediaPlayer.run()

if __name__ == "__main__":
    main()
