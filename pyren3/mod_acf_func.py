#!/usr/bin/env python3

import sys
import os
import time
import mod_globals
import zipfile
import pickle
import shutil

errone   = {}
acfFile  = ""
zip      = None
zipflist = []

class ACE():
  VEH = ""
  REF = ""
  UCE = ""
  NOM = ""
  cfg = []
  dat = {}
  req = {}

  def __init__(self):  
    self.VEH = ""
    self.REF = ""
    self.UCE = ""
    self.NOM = ""
    self.cfg = []
    self.req = {}
    self.dat = {}

def get_alternative_refs( platform ):
  #finds more frequent use of ref1 from --ref otion in REF.DAT
  if mod_globals.opt_ref =='': return {}

  start_time = time.time()

  res = {}
  alt = {}
  for aref in mod_globals.opt_ref.split(';'):
    aref = aref.strip()
    if (len(aref)==23 or len(aref)==24) and ' ' in aref:
      #ref pair defined compleatle
      idf,refPair = aref.split(':')
      res[idf] = refPair
      continue
    if ':' in aref:
      idf,ref1 = aref.split(':')
    else:
      print("ERROR in --ref option. ECU family not defined (" + aref + ")" )
      continue
    for r in ref1.split(','):
      if len(r)==10:
        alt[idf+':'+r] = {}
      else:
        print("ERROR. Wrong --ref option", aref )
  
  #find in REF.DAT
  try:
    vindir = '../BVMEXTRACTION/'+platform+'/'
    ref_name = 'REF.dat'
    for fn in os.listdir(vindir):
      if fn.upper()=='REF.DAT': ref_name = fn
    rz = open(vindir+ref_name,'r')
    reflist = rz.read().split('\n')
    rz.close()
    for l in reflist:
      if l == '': continue
      ll = l[l.find(':')+1:].split(';')
      for e in ll:
        for a in alt.keys():
          if e.startswith(a):
            if e not in alt[a].keys():
              alt[a][e] = 1
            else:
              alt[a][e] += 1
  except:
    print("\n\nREF.dat is absent!!!\n\n")

  #now we have to remove emty records in alt
  for a in alt.copy().keys():
    if len( alt[a] ) == 0:
      del alt[a]
  
  gmax = {}
  maxval = 0
  for a in alt.keys():
    max = list(alt[a].keys())[0]
    maxval = alt[a][max]
    for ak in alt[a].keys():
      if alt[a][ak]>alt[a][max]: 
        max = ak
        maxval = alt[a][ak]
    idf,refPair = max.split(':')
    if idf in gmax.keys() and maxval < gmax[idf]:
      continue
    else:
      gmax[idf] = maxval
    res[idf] = refPair

  end_time = time.time()
  print( "Ref search took:", int(end_time-start_time), " sec" )
  print( res )

  return res

    
def acf_find_in_sirev( ref2, platform ):
  global errone
  global zip
  global zipflist
  
  platform = bytes(platform, 'utf-8')
  ref2 = bytes(ref2, 'utf-8')

  if len(list(errone.keys()))==0:
    se=zip.open('SIREV_ERRONE.dat')
    cont=se.read()
    for l in cont.split(b'\n'):
      li = l.split(b'/')
      if len(li)==6 and li[0]==platform:
        errone[li[2]] = li[3]
  
  while( ref2 in list(errone.keys())):
    #print('e:',ref2,errone[ref2] )
    ref2 = errone[ref2]
    
  return ref2.decode("utf-8")

def acf_loadModules( de, refdata, platform ):
  ''' load modules from CONFIG database'''
  
  global acfFile
  global zip
  global zipflist
  
  for file in os.listdir(".."):
    if file.endswith('.acf'):
      acfFile = '../'+file
      break
      
  if acfFile=='':
    print("ERROR: Configuration database not found")
    exit()
  else:
    print("Configuration database: ", acfFile)
    
  zip=zipfile.ZipFile(acfFile)
  zip.setpassword(b'A710FBD006342FC8')
  zipflist = zip.namelist()

  module_list = []

  #first check mod_globals.opt_ref for alternatives
  alt = get_alternative_refs( platform )

  for r in refdata.split(';'):
    try:
      idf, r1 = r.split(':')
      if idf in alt.keys():
        ref1,ref2 = alt[idf].split(' ')
      else:
        ref1,ref2 = r1.split(' ')
    except:
      continue

    if ref2+'.dat' not in zipflist:
      ref2 = acf_find_in_sirev( ref2, platform )

    m = {}

    m['idf'] = idf
    m['sref'] = ref2
    m['mo']=''
    m['dst'] = ''
    m['pin'] = 'undef'
    m['idRx'] = ''
    m['idTx'] = ''
    m['ecuname'] = ''
    m['startDiagReq'] = '10C0'
    if ref2 + '.dat' in zipflist:
      modf = zip.open(ref2 + '.dat')
      m['mo'] = pickle.load(modf)

    for k in de:
      if k['idf']==idf:
        m['pin'] = k['pin']
        m['dst'] = k['dst']
        if 'idRx' in k.keys() and 'idTx' in k.keys():
          m['idRx'] = k['idRx']
          m['idTx'] = k['idTx']
        m['startDiagReq'] = k['startDiagReq']
        m['ecuname'] = k['ecuname']
        m['brp'] = k['brp']
        break

    module_list.append(m)

  return module_list
