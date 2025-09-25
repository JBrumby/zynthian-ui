#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
#
# Minimalistic Zynthian Control Device Driver for M-Audio Keystation Pro 88
# Designed for Zynthian with touch screen (but without rotary encoders)
# The device driver can control the GUI using the 4 knobs
# The Keystation Pro 88 has no LEDs, so no visual feedback is possible on the device
# It also doesn't send key on/off messages, only program change messages on press,
# making it impossible to detect long and short presses.
# Rotary encoders are simulated with knobs 18, 19, 10, and 11
# This sample driver demonstrates how easy it is to write a custom driver
# for a specific MIDI controller

# Note: When this driver throws an exception, the MIDI event is still processed
# as if midi_event() returned "False". This was noticed when there was an error
# in the send_midi function (zynseq library was not imported).
# This requires further investigation

import logging

# for changing events with mididings
import mididings
from functools import partial # needed for function params in mididings process
# we need the scales
from zyngine.ctrldev.zynthian_ctrldev_base_scale import _MODES

from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_base
from zynlibs.zynseq import zynseq  # For sending MIDI directly from this driver

logger = logging.getLogger('zynthian')

class zynthian_ctrldev_keystation_pro_88_mk1(zynthian_ctrldev_base):
    # Device identification
    # dev_id = ["Keystation Pro 88"]  # Optional
    
    # There's no straightforward way to list device IDs on the Linux console
    # The device IDs in Zynthian differ from those found in the Linux console
    # Debugging is the easiest way to find the correct device IDs
    # You can try using the device name with " IN 1" and " IN 2" suffixes
    
    dev_ids = ["Keystation Pro 88 IN 1"]  # These values are essential

    # driver_name = "Keystation Pro 88 Minimal"  # Optional, for log information
    # driver_description = "Minimalistic Zynthian Control Device Driver for M-Audio Keystation Pro 88" 
    # driver_version = "0.1" 
    # True if input device must be unrouted from chains when driver is loaded
    # Alternately specific MIDI channels can be unrouted by specifying a bitwise mask,
    # For instance, use "0b0000000000001111" to unroute MIDI channels 0 to 3.
    # unroute_from_chains = True 
    # keystation sends on channel 1 to 4 its note events. 4 different split keyboard setup on hardware device
    # I want to use channel16 for this driver to get its information by mididings, so I unroute this only channel
    unroute_from_chains = 0b0000_0000_0001_0000
    # unroute_from_chains = False # all is working as intended
    # now nothing than events on channel 16 reach this driver! 
    # without routing in mididings it wount work anymore
    
    # copied from an instance of Harmony()
    # target_mode = [0, 2, 4, 5, 7, 9, 11] #  mode major
    # [48, 50, 52, 53, 47, 48, 50, 52, 53, 55, 57, 59, 52, 53, 55, 57, 59, 60, 62, 64, 57, 59, 60, 62, 64, 65, 67, 69, 62, 64, 65, 67, 69, 71, 72, 74, 67, 69, 71, 72, 74, 76, 77, 79, 72, 74, 76, 77, 79, 81, 83, 84, 77, 79, 81, ...]
    
    
    # Helper variables for potentiometers. Workaround because ZYNPOT_ABS didn't work
    zynpot_0 = 0
    zynpot_1 = 0
    zynpot_2 = 0
    zynpot_3 = 0    
    
    # MIDI event types
    EV_NOTE_OFF = 0x8  # 3 bytes
    EV_NOTE_ON = 0x9  # 3 bytes
    EV_AFTERTOUCH = 0xA  # 3 bytes (polyphonic = per note)
    EV_CC = 0xB  # 3 bytes
    EV_PC = 0xC  # 2 bytes
    EV_CHAN_PRESS = 0xD  # 2 bytes
    EV_PITCHBEND = 0xE  # 3 bytes: ev[1] = LSB 0-127; ev[2] = MSB 0-127
    EV_SYSTEM = 0xF  # System type = ev[0] & 0x0F
    
    
    def __init__(self, state_manager, idev_in, idev_out=None):
        self.zynseq = state_manager.zynseq # we need to send midi events to zynthian
        super().__init__(state_manager, idev_in, idev_out)
        return
    
    ###########################################################################################################
################ mididings

# The midiproc task itself. It runs in a spawned process.
    def midiproc_task(self):
        self.midiproc_task_reset_signal_handlers()
        
              
        MODES = _MODES
        # scale_targets = MODES["Minor"]
        # scale_targets = MODES["Hungarian Minor"]
        scale_targets = [0, 2, 3, 6, 7, 8, 11]
        
        mididings.config(
            backend='jack-rt',
            client_name=self.midiproc_jackname,
            in_ports=1,
            out_ports=1,
        )
        
        
        # get parameters
        def translate_scale(ev, distance = None):
            # print(distance)
            note = ev.note
            # print(note)
            
            octave = note // 12
            # print(f"octave: {octave}")
            
            chroma_note = note % 12
            # print(f"chroma_note: {chroma_note}")
            
            # Mapping: get white keys, remove black keys from piano notes
            key_map = (0, None, 1, None, 2, 3, None, 4, None, 5, None, 6)
    
            if chroma_note < 0 or chroma_note >= len(key_map): # is map right initialized
                return None  # for shorter modes with less then 7 tones
            
            chroma_note_cleaned = key_map[chroma_note]
            if chroma_note_cleaned == None: # is black key.
                return None # discard event
            
            # print(f"chroma_note_cleaned: {chroma_note_cleaned}")
            if not 0 <= chroma_note_cleaned < len(scale_targets): # wrong scale_map values
                return None
            
            note_new = scale_targets[chroma_note_cleaned] + (octave * 12)
            # print(f"Heureka target note is {note_new}")
            ev.note = note_new
            return ev
        
        mididings.run(
            [
                # #mididings.Pass() // (mididings.Channel(2) >> (mididings.Pass() // mididings.Transpose(4) // mididings.Transpose(7)))
                # mididings.Pass() //  mididings.Transpose(4) //  mididings.Transpose(7)
            

                # with params
                ## mididings.Filter(mididings.PROGRAM) // # all but note events
                #mididings.Channel(5) // # all to channel 5 which will not be routed
                
                mididings.Filter(mididings.CTRL) >> mididings.Channel(5),  # jst CTRLS to keyboard driver   
                
                mididings.Filter(mididings.NOTEON | mididings.NOTEOFF ) >> 
                    mididings.Process( partial( translate_scale, distance = None) ) ,
                    
                ~mididings.Filter(mididings.NOTEON | mididings.NOTEOFF) >> mididings.Pass()
                    
            ]                  
        )

    
    def midi_event(self, ev):
        # return False
        """MIDI event handler for Keystation Pro 88"""
        filter_chan_5 = 5-1
        if not ev[0] & 0x0F == filter_chan_5:
            return False
        
        evtype = (ev[0] >> 4) & 0x0F
        
        if len(ev) == 3:
            logger.debug(f"MIDI event received: {ev} {ev[0]} {ev[1]} {ev[2]}")
        
        if len(ev) > 0:
            status = ev[0] & 0xF0  # MIDI message type (note on, note off, control change, etc.)
            # channel = ev[0] & 0x0F  # Not used
        
        # not more necessary. Mididings is working
        # # Forward certain events directly to MIDI output
        # if evtype in [self.EV_NOTE_ON, self.EV_NOTE_OFF, self.EV_AFTERTOUCH, self.EV_PITCHBEND]:
        #     return self.send_midi(ev)
        
        # Process 3-byte events (control changes)
        if len(ev) == 3:
            data1 = ev[1]  # Note number or controller number
            data2 = ev[2]  # Note velocity or controller value
            
            # Simulate rotary encoders with knobs
            # We send the difference between the last value and the new value
            # to the state manager ("ZYNPOT_ABS" would be easier but didn't work)
            # The state manager will handle the rest
            # We have to store the last value of each knob
            # We have 4 knobs for 4 virtual rotary encoders:
            # Knob 18 -> ZYNPOT 0
            # Knob 19 -> ZYNPOT 1
            # Knob 10 -> ZYNPOT 2
            # Knob 11 -> ZYNPOT 3
            
            # Note: First use of a knob will jump from 0 to the current knob value
            # There's currently no way to get the initial value of the knob at startup
            
            # 0xB0 is Control Change on MIDI Channel 1
            if status == 0xB0:
                if data1 == 104:  # Knob 18 in "Preset-Recall 10"
                    pot = data2 - self.zynpot_0  # Calculate relative change
                    self.zynpot_0 = data2  # Store new value for next change
                    self.state_manager.send_cuia("ZYNPOT", [0, pot])
                    return True  # Event processed
                
                elif data1 == 105:  # Knob 19 in "Preset-Recall 10"
                    pot = data2 - self.zynpot_1
                    self.zynpot_1 = data2
                    self.state_manager.send_cuia("ZYNPOT", [1, pot])
                    return True
                
                elif data1 == 85:  # Knob 10 in "Preset-Recall 10"
                    pot = data2 - self.zynpot_2
                    self.zynpot_2 = data2
                    self.state_manager.send_cuia("ZYNPOT", [2, pot])
                    return True
                
                elif data1 == 86:  # Knob 11 in "Preset-Recall 10"
                    pot = data2 - self.zynpot_3
                    self.zynpot_3 = data2
                    self.state_manager.send_cuia("ZYNPOT", [3, pot])
                    return True
        
        # Process program change events (buttons)
        # Note: Using buttons on Keystation 88 Pro MK1 for "back" and "OK" is not ideal
        # because all buttons send only a program change when pressed, with no way to
        # detect long vs short presses
        # if len(ev) >= 2:
        #     if ev[0] & 0xF0 == 0xC0:  # Program Change event
        #         data1 = ev[1]  # Program number
                
        #         # Map program changes to UI actions
        #         if data1 == 0:  # Button "Back"
        #             self.state_manager.send_cuia("BACK")
        #             return True
                
        #         elif data1 == 1:  # Button "OK"
        #             self.state_manager.send_cuia("SELECT")
        #             return True
        
        return False # nothing to do. mididings did its thing  # Event not processed by this driver
    
    def send_midi(self, ev):
        """Send MIDI event to active chain"""
        return False
        chain = self.chain_manager.get_active_chain()
        
        if chain is None or chain.midi_chan is None:
            return False
        
        status = (ev[0] & 0xF0) | chain.midi_chan
        # zynseq.libseq.sendMidiCommand(status, ev[1], ev[2]) # was anytime working
        self.zynseq.libseq.sendMidiCommand(status, ev[1], ev[2])
        # self.chain_manager
        # self.state_manager
        ###### self.zynseq.libseq.sendMidiCommand(status, ev[1], ev[2])
        return True
