#!/usr/bin/env python3

import sys
import os
import time
import mod_globals
import mod_elm
import shutil
import pickle

from mod_mtc import acf_MTC_finde
from mod_mtc import acf_MTC_and
from mod_mtc import acf_MTC_compare

from   mod_utils    import loadDumpToELM
from   mod_utils    import hex_VIN_plus_CRC
from   mod_utils    import pyren_encode

def acf_pack_command( write, req, dat, cmd, tram, mask ):
  
  if write:
    FB = int(req.SentDI[dat].FirstByte)-1
  else:
    FB = int(req.ReceivedDI[dat].FirstByte)-1
  
  if len(cmd)<req.MinBytes*2:
    cmd = cmd + '0'*(req.MinBytes*2-len(cmd))
    
  #print req
  #print dat
  #print cmd
  #print FB
  #print tram
  #print mask
  
  i = 0
  l = len(mask)//2
  
  while( i<l ):
    try:
      cb = int(cmd[(FB+i)*2:(FB+i)*2+2],16)
    except:
      cb = 0
    tb = int(tram[i*2:i*2+2],16)
    mb = int(mask[i*2:i*2+2],16)^0xFF
    #print 'cb:%d tb:%d mb:%d' % (cb,tb,mb)
    rb = (cb & mb) | tb
    rh = hex(rb).upper()[2:].zfill(2)
    #print 'rh:',rh
    cmd = cmd[:(FB+i)*2]+rh+cmd[(FB+i)*2+2:]
    i = i + 1
    
  #print cmd
  
  return cmd

def acf_form_commands( m, cu, op ):

  ace = m['mo']
  
  if len( cu.RR ) > 0:
    if cu.RR not in list(m['acf_rc'].keys()) and cu.RR in list(ace.req.keys()):
      m['acf_rc'][cu.RR] = ace.req[cu.RR].ReplyBytes
    m['acf_rc'][cu.RR] = acf_pack_command( False, ace.req[cu.RR], cu.DR, m['acf_rc'][cu.RR], op.TR1, op.MR)
  
  if len( cu.RW ) > 0:
    if cu.RW not in list(m['acf_wc'].keys()) and cu.RW in list(ace.req.keys()):
      m['acf_wc'][cu.RW] = ace.req[cu.RW].SentBytes
    m['acf_wc'][cu.RW] = acf_pack_command( True,  ace.req[cu.RW], cu.DW, m['acf_wc'][cu.RW], op.TW, op.MW)
    ace.req[cu.RW].SentDI[cu.DW].val = op.VW + ' #[' + cu.TE + ' : ' + op.TEX + '](' + op.MTC + ')'

def acf_MTC_generateDefaults( m, mtc ):
  """ m - module definition map """
  ''' mtc - list of options     '''
  ''' this function generates default values'''
  
  if m['mo']=='':
    return
    
  ace = m['mo']
  
  m['acf_rc'] = {}
  m['acf_wc'] = {}
  
  #print ace.VEH
  #print ace.REF
  #print ace.NOM
  
  for cu in ace.cfg:
    #print '-'*35,'\n', cu.DI
    
    #check kabsence
    if len(cu.kabs)>0:
      res = acf_MTC_compare(cu.kabs[0], mtc)
      if res:
        print('kab:', cu.kabs[0], '[', res, ']')
        print('!'*50)
        continue    
    
    #check every mtc
    for op in cu.opts:
      res = acf_MTC_compare(op.MTC, mtc)
      if res:
        acf_form_commands( m, cu, op )
        break
  
  ddtxml = ace.NOM
  if ddtxml.upper().endswith('.XML'):
    ddtxml = ddtxml[:-4]

  ddtxml = ddtxml.replace('\\', '_')

  if m['ecuname']=='':
    m['ecuname'] = m['dst']

  #dumpn1 = mod_globals.mtcdir+'/dumps/'+str(int(time.time()))+'_'+ddtxml+'.txt'
  #dumpn2 = mod_globals.mtcdir+'/dumps/'+str(int(time.time()))+'_'+m['ecuname']+'.txt'
  dumpn1 = mod_globals.mtcdir+'/dumps/0000000000_'+ddtxml+'.txt'
  dumpn2 = mod_globals.mtcdir+'/dumps/0000000000_'+m['ecuname']+'.txt'

  df1 = open(dumpn1,'wt')

  #print "--------------- Read Commands --------------------"
  # save read commands as a dump files
  for k in list(m['acf_rc'].keys()):
    #print k
    result = m['acf_rc'][k]
    r = ' '.join(a+b for a,b in zip(result[::2], result[1::2]))
    line =  m['mo'].req[k].SentBytes+':'+r.strip()
    df1.write( line+'\n' )
  df1.close()
  #shutil.copyfile(dumpn1,dumpn2)
  #print dumpn1
  #print dumpn2

  scriptn = mod_globals.mtcdir+'/scripts/cmd_'+m['pin']+'_'+m['idf']+'_'+mod_globals.vin[-4:]+'_'+m['sref']+'.cmd'
  sf = open(scriptn,'wt')

  #print "--------------- Write Commands --------------------"

  # write preamble
  sf.write('# ' + mod_globals.vin + '\n\n')
  sf.write('$addr = ' + m['dst'] +'\n\n')
  sf.write('#idTx = ' + m['idTx'] + ' idRx = ' + m['idRx'] + '\n\n')
  if m['pin'].startswith('can'):
    if m['brp']=='0':
      sf.write('can500  # init can macro\n\n')
    else:
      sf.write('can250  # init can macro\n\n')
  else:
    sf.write('fast  # init iso macro\n\n')
  sf.write('delay 1\n\n')
  sf.write('# open session\n')
  sf.write('session ' + m['startDiagReq'] + '\n\n')
  sf.write('# configuration\n')

  # save write commands
  for k, v in sorted( list(m['acf_wc'].items()), key=lambda x_y: x_y[1] ):
    if mod_globals.opt_verbose or mod_globals.opt_verbose2:
      try:
        sf.write('#'*60 + '\n')
        sf.write('# ' + k + '\n')
      except:
        pass
    if mod_globals.opt_verbose2:
      for di in sorted(list(m['mo'].req[k].SentDI.values()), key=lambda x: x.FirstByte * 8 + x.BitOffset):
        try:
          sf.write(pyren_encode('##     ' + di.Name + ' = ' + di.val + '\n'))
        except:
          try:
            sf.write(pyren_encode('##     ' + di.Name + ' = UNDEFINED\n'))
          except:
            pass
    sf.write(m['acf_wc'][k]+'\n')


  # write trailer
  sf.write('\n# VIN programming !!!check the command!!!\n')
  sf.write('#2EF190' + hex_VIN_plus_CRC(mod_globals.vin, False) +'\n')
  sf.write('#3B81' + hex_VIN_plus_CRC(mod_globals.vin, True) +'\n')
  sf.write('\n# reset ecu or disconnect the battary!!!check the command!!!\n')
  sf.write('#1101\n\n')
  sf.write('exit\n')

  sf.close()

  
def acf_MTC_findDiff( m, mtc, elm ):
  ''' m - module definition map '''
  ''' mtc - list of options     '''
  ''' this function finds the diff beetwen generated and real values'''
  
  if m['mo']=='':
    return
    
  ace = m['mo']
  
  # init elm
  if mod_globals.opt_demo: #try to load dump
    loadDumpToELM( m['ecuname'], elm )
  else:
    if m['pin'].lower()=='can':
      elm.init_can()
      elm.set_can_addr( m['dst'], m )
    else:
      elm.init_iso()
      elm.set_iso_addr( m['dst'], m )
    elm.start_session( m['startDiagReq'] )
     
  for cu in ace.cfg:
    print('-'*35,'\n', cu.TE)
    print(cu.RR)
    
    if cu.RR=='': continue
    
    #check kabsence
    if len(cu.kabs)>0:
      res = acf_MTC_compare(cu.kabs[0], mtc)
      if res:
        #print  'kab:', cu.kabs[0], '[', res, ']'   
        #print '!'*50
        continue    
    
    #check every mtc
    for op in cu.opts:
      res = acf_MTC_compare(op.MTC, mtc)
      if res:
        rsp = elm.request( ace.req[cu.RR].SentBytes, ace.req[cu.RR].ReplyBytes[:2] )
        print(ace.req[cu.RR].SentBytes, rsp)
        #acf_form_commands( m, cu, op )
        break

def acf_MTC_optinInfluence( m, option, allmtc ):
  ''' m - module definition map '''
  ''' option - option name from MTC list '''
  ''' this function finds dependent parameters in one module'''

  if m['mo']=='':
    return
    
  ace = m['mo']
  out = ''

  for cu in ace.cfg:

    cuTE   = cu.TE
    opMTC  = ''
    opVW   = ''
    opTEX  = ''
    
    
    #check kabsence
    if len(cu.kabs)>0:
      res = acf_MTC_compare(cu.kabs[0], option)
      if res:
        #print  'kab:', cu.kabs[0], '[', res, ']'   
        #print '!'*50
        continue    
    
    #check every mtc
    for op in cu.opts:
      if option not in op.MTC: continue
      res = acf_MTC_compare(op.MTC, allmtc)
      if res:
        if op.MTC.startswith('SAUF'): continue
        out = out + '%-70s;%-15s;%-15s;%s\n'%(cu.DI, op.VW, op.MTC, op.TEX)
  
  return out
  
def acf_MTC_optionsExplorer( de, option, allmtc ):
  ''' de - list of all ecus '''
  ''' option - option name from MTC list '''
  ''' this function finds dependent parameters in every module'''
  
  res = []

  res.append(f'################### {option:10}  #########################')
  
  for m in de:
    if 'sref' not in list(m.keys()) or m['sref']=='': continue
    if 'sref' in list(m.keys()):
      if 'mo' in list(m.keys()) and m['mo']!='':    
        out = acf_MTC_optinInfluence( m, option, allmtc )
        if len(out)>0:
          res.append(f"---------------------  Family : {m['idf']} : {m['fam_txt']}")
          res.append(out)

  return res       
  
  
  
