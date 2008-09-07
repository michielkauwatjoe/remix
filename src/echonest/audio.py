"""
A module for manipulating audio files and their associated Echo Nest
Analyze API analyses.

AudioAnalysis class by Joshua Lifton 2008-09-07.  Everything else by
Robert Ochshorn on 2008-06-06.
"""

__version__ = "$Revision: 0 $"
# $Source$

import commands, os, struct, tempfile, wave
import numpy, Numeric
import echonest.web.analyze as analyze;

class AudioAnalysis(object) :
    """
    This class wraps echonest.web to allow transparent caching of the
    audio analysis of an audio file.

    For example, the following script will display the bars of a track
    twice:
    
        from echonest import *
        a = audio.AudioAnalysis('YOUR_TRACK_ID_HERE')
        a.bars
        a.bars

    The first time a.bars is called, a network request is made of the
    Echo Nest anaylze API.  The second time time a.bars is called, the
    cached value is returned immediately.

    An AudioAnalysis object can be created using an existing ID, as in
    the example above, or by specifying the audio file to upload in
    order to create the ID, as in:

        a = audio.AudioAnalysis(filename='FULL_PATH_TO_AUDIO_FILE')
    """

    # Any variable in this listing is fetched over the network once
    # and then cached.  Calling refreshCachedVariables will force a
    # refresh.
    CACHED_VARIABLES = ( 'bars', 
                         'beats', 
                         'duration', 
                         'end_of_fade_in', 
                         'key',
                         'loudness',
                         'metadata',
                         'mode',
                         'sections',
                         'segments',
                         'start_of_fade_out',
                         'tatums',
                         'tempo',
                         'time_signature' )

    def __init__( self, audio ) :
        """
        Constructor.  If the arugment is a valid local path or a URL,
        the track ID is generated by uploading the file to the Echo
        Nest Analyze API.  Otherwise, the argument is assumed to be
        the track ID.

        @param audio A string representing either a path to a local
        file, a valid URL, or the ID of a file that has already been
        uploaded for analysis.
        """

        # Error checking of constructor arguments.
        if type(audio) is not str :
            # Argument is invalid.
            raise TypeError("Argument 'audio' must be a string representing either a filename or track ID.")
        elif os.path.isfile(audio) or '.' in audio :
            # Argument is either a filename or URL.
            doc = analyze.upload(audio)
            self.id = doc.getElementsByTagName('thingID')[0].firstChild.data
        else :
            # Argument is a track ID.
            self.id = audio
            

        # Initialize cached variables to None.
        for cachedVar in AudioAnalysis.CACHED_VARIABLES : 
            self.__setattr__(cachedVar, None)



    def refreshCachedVariables( self ) :
        """
        Forces all cached variables to be updated over the network.
        """
        for cachedVar in AudioAnalysis.CACHED_VARIABLES : 
            self.__setattr__(cachedVar, None)
            self.__getattribute__(cachedVar)
        


    def __getattribute__( self, name ) :
        """
        This function has been modified to support caching of
        variables retrieved over the network.
        """
        if name in AudioAnalysis.CACHED_VARIABLES :
            if object.__getattribute__(self, name) is None :
                getter = analyze.__dict__[ 'get_' + name ]
                value = getter(object.__getattribute__(self, 'id'))
                self.__setattr__(name, value)
        return object.__getattribute__(self, name)





class AudioData():

    def __init__(self, ndarray=None, shape=None,samplerate=44100,numchannels=2):
        self.samplerate = samplerate
        self.numchannels = numchannels
        
        if shape is None and isinstance(ndarray, numpy.ndarray):
            self.data = numpy.zeros(ndarray.shape, dtype=numpy.int16)
        elif shape is not None:
            self.data = numpy.zeros(shape, dtype=numpy.int16)
        else:
            self.data = None
        self.endindex = 0
        if ndarray is not None:
            self.endindex = len(ndarray)
            self.data[0:self.endindex] = ndarray



    def __getitem__(self, index):
        "returns individual frame or the entire slice as an AudioData"
        if isinstance(index, float):
            index = int(index*self.samplerate)
        elif hasattr(index, "start") and hasattr(index, "duration"):
            index =  slice(index.start, index.start+index.duration)

        if isinstance(index, slice):
            if ( hasattr(index.start, "start") and 
                 hasattr(index.stop, "duration") and 
                 hasattr(index.stop, "start") ) :
                index = slice(index.start.start, index.stop.start+index.stop.duration)

        if isinstance(index, slice):
            return self.getslice(index)
        else:
            return self.getsample(index)



    def getslice(self, index):
        if isinstance(index.start, float):
            index = slice(int(index.start*self.samplerate), int(index.stop*self.samplerate), index.step)
        return AudioData(self.data[index],samplerate=self.samplerate)



    def getsample(self, index):
        if isinstance(index, int):
            return self.data[index]
        else:
            #let the numpy array interface be clever
            return AudioData(self.data[index])



    def __add__(self, as2):
        if self.data is None:
            return AudioData(as2.data.copy())
        elif as2.data is None:
            return AudioData(self.data.copy())
        else:
            return AudioData(numpy.concatenate((self.data,as2.data)))



    def append(self, as2):
        "add as2 at the endpos of this AudioData"
        self.data[self.endindex:self.endindex+len(as2)] = as2.data[0:]
        self.endindex += len(as2)



    def __len__(self):
        if self.data is not None:
            return len(self.data)
        else:
            return 0



    def save(self, filename=None):
        "save sound to a wave file"

        if filename is None:
            foo,filename = tempfile.mkstemp(".wav")

        ###BASED ON SCIPY SVN (http://projects.scipy.org/pipermail/scipy-svn/2007-August/001189.html)###
        fid = open(filename, 'wb')
        fid.write('RIFF')
        fid.write('\x00\x00\x00\x00')
        fid.write('WAVE')
        # fmt chunk
        fid.write('fmt ')
        if self.data.ndim == 1:
            noc = 1
        else:
            noc = self.data.shape[1]
        bits = self.data.dtype.itemsize * 8
        sbytes = self.samplerate*(bits / 8)*noc
        ba = noc * (bits / 8)
        fid.write(struct.pack('lhHLLHH', 16, 1, noc, self.samplerate, sbytes, ba, bits))
        # data chunk
        fid.write('data')
        fid.write(struct.pack('l', self.data.nbytes))
        self.data.tofile(fid)
        # Determine file size and place it in correct
        #  position at start of the file. 
        size = fid.tell()
        fid.seek(4)
        fid.write(struct.pack('l', size-8))
        fid.close()

        return filename



def load(file, datatype=numpy.int16, samples=None, channels=None):
    "make AudioData from file"
    if samples is None or channels is None:
        #force samplerate and num channels to 44100 hz, 2
        samples, channels = 44100, 2
        foo, dest = tempfile.mkstemp(".wav")
        cmd = "ffmpeg -y -i \""+file+"\" -ar "+str(samples)+" -ac "+str(channels)+" "+dest
        print cmd
        parsestring = commands.getstatusoutput(cmd)
        parsestring = commands.getstatusoutput("ffmpeg -i "+dest)
        samples, channels = audiosettingsfromffmpeg(parsestring[1])
        file = dest

    w = wave.open(file, 'r')
    raw = w.readframes(w.getnframes())
    
    sampleSize = w.getnframes()*channels
    data = Numeric.array(map(int,struct.unpack("%sh" %sampleSize,raw)),Numeric.Int16)

    numpyarr = numpy.array(data, dtype=numpy.int16)
    #reshape if stereo
    if channels == 2:
        numpyarr = numpy.reshape(numpyarr, (w.getnframes(), 2))
    
    return AudioData(numpyarr,samplerate=samples,numchannels=channels)



def audiosettingsfromffmpeg(parsestring):
    parse = parsestring.split('\n')
    freq, chans = 44100, 2
    for line in parse:
        if "Stream #0" in line and "Audio" in line:
            segs = line.split(", ")
            for s in segs:
                if "Hz" in s:
                    print "FOUND: "+str(s.split(" ")[0])
                    freq = int(s.split(" ")[0])
                elif "stereo" in s:
                    print "STEREO"
                    chans = 2
                elif "mono" in s:
                    print "MONO"
                    chans = 1

    return freq, chans



def getpieces(audioData, segs):
    "assembles a list of segments into one AudioData"
    #calculate length of new segment
    dur = 0
    for s in segs:
        dur += int(s.duration*audioData.samplerate)

    dur += 100000 #another two seconds just for goodwill...

    #determine shape of new array
    if len(audioData.data.shape) > 1:
        newshape = (dur, audioData.data.shape[1])
        newchans = audioData.data.shape[1]
    else:
        newshape = (dur,)
        newchans = 1

    #make accumulator segment
    newAD = AudioData(shape=newshape,samplerate=audioData.samplerate, numchannels=newchans)

    #concatenate segs to the new segment
    for s in segs:
        newAD.append(audioData[s])

    return newAD
