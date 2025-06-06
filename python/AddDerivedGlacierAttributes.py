﻿#-------------------------------------------------------------------------------
# Name: AddDerivedGlacierAttributes.py
# Purpose: This tool generates the derived attributes of palaeoglaciers.
#          The inputs of this tool include the divided glacier outlines, the reconstruction method,
#          the reconstructed ice surface raster, and the reconstructed ice thickness raster for
#          paleoglaciers. Other inputs also include the elevation bins for AAR and AABR methods to
#          calculate the ELAs and the AAR and AABR ratios. This tool derived all attributes based
#          on provided reconstruction method, ice surface and ice thickness rasters. The methods
#          to derive A3D, R3d2D, Z_min, Z_max, Z_range, Z_mean, Z_mid, Mean_slope, Mean_aspect,
#          Hypsomax, and HI are based on the methods described in Li et al. (2024). This tool also
#          incorporates the four methods described in (Pellitero et al. 2015) to derive the ELA of
#          the palaeoglacier, MGE, AAR, AA, and AABR. The default elevation bin is 20 m, and AAR ratio
#          of 0.58, and AABR ratio of 1.56. The mean, std, median and max thickness are derived based
#          on zonal statistics of the ice thickness raster for each paleoglacier outline.
#
# Author: Dr. Yingkui Li
# Created:     10/08/2023-02/21/2025
# Department of Geography, University of Tennessee
# Knoxville, TN 37996
#-------------------------------------------------------------------------------

# Import arcpy module
from __future__ import division
import locale
import arcpy, sys
from arcpy import env
from arcpy.sa import *
#import numpy
import numpy as np

try:
    import numba
except:
    os.system("python -m pip install numba")
    #!pip install numba
    import numba

from numba import jit, prange

locale.setlocale(locale.LC_ALL,"")#sets local settings to decimals
arcpy.env.overwriteOutput = True
arcpy.env.XYTolerance= "0.01 Meters"

ArcGISPro = 0
arcpy.AddMessage("The current python version is: " + str(sys.version_info[0]))
if sys.version_info[0] == 2:  ##For ArcGIS 10, need to check the 3D and Spatial Extensions
    try:
        if arcpy.CheckExtension("Spatial")=="Available":
            arcpy.CheckOutExtension("Spatial")
        else:
            raise Exception ("not extension available")
            #print "not extension available"
    except:
        raise Exception ("unable to check out extension")
        #print "unable to check out extension"

    try:
        if arcpy.CheckExtension("3D")=="Available":
            arcpy.CheckOutExtension("3D")
        else:
            raise Exception ("not extension available")
            #print "not extension available"
    except:
        raise Exception ("unable to check out extension")
        #print "unable to check out extension"
elif sys.version_info[0] == 3:  ##For ArcGIS Pro
    ArcGISPro = 1
    #pass ##No need to Check
else:
    raise Exception("Must be using Python 2.x or 3.x")
    exit()   

temp_workspace = "in_memory"  
if ArcGISPro:
    temp_workspace = "memory"

@jit(nopython=True, parallel=True)
def ELA_AAR_MGE(EleArr, interval, ratio):
    minimum = np.min(EleArr)
    maximum = np.max(EleArr)
    
    maxalt = int(maximum + interval)
    minalt = int(minimum - interval)

    # Create array of bin edges
    Elelist = np.arange(minalt, maxalt + interval, interval)
    
    # Calculate histogram
    H, X1 = np.histogram(EleArr, bins=Elelist)
    dx = X1[1] - X1[0]


    Area3D_arr = np.cumsum(H) * dx
    
    superf_total = np.max(Area3D_arr)  # Get the total surface
    Area3D_arr = superf_total - Area3D_arr

    ELA = superf_total * ratio  # Get the surface above the ELA
    kurowski = superf_total * 0.5

    # Find indices where values meet conditions
    ela_idx = -1
    kur_idx = -1
    min_ela_diff = np.inf
    min_kur_diff = np.inf
    
    for i in range(len(Area3D_arr)):
        val = Area3D_arr[i]
        
        # Check for ELA condition
        if val <= ELA:
            diff = ELA - val
            if diff < min_ela_diff:
                min_ela_diff = diff
                ela_idx = i
                
        # Check for Kurowski condition
        if val <= kurowski:
            diff = kurowski - val
            if diff < min_kur_diff:
                min_kur_diff = diff
                kur_idx = i

    # Calculate results
    ELA_AAR = Elelist[ela_idx] + (interval/2) + interval
    ELA_MGE = Elelist[kur_idx] + (interval/2) + interval
    
    return ELA_AAR, ELA_MGE

@jit(nopython=True, parallel=True)
def ELA_AA_AABR(EleArr, interval, AABRratio):
    # Calculate min/max with buffer
    minimum = np.min(EleArr)
    maximum = np.max(EleArr)
    maxalt = int(maximum + interval)
    minalt = int(minimum - interval)

    # Optimized bin calculation
    num_bins = int(np.ceil((maxalt - minalt) / interval))
    maxValue = minalt + interval * num_bins - interval/2
    list_altitudes = np.linspace(minalt + interval/2, maxValue, num_bins)
    
    # Create histogram bins
    Elelist = np.linspace(minalt, minalt + interval * (num_bins-1), num_bins)
    
    # Calculate histogram and cumulative area
    H, X1 = np.histogram(EleArr, bins=Elelist)
    dx = X1[1] - X1[0]
    Area3D_arr = np.cumsum(H) * dx * 100  # Convert to percentage

    # AA Calculation
    superf_total = np.max(Area3D_arr)
    resta = np.diff(Area3D_arr)
    finalmulti = np.sum(resta * list_altitudes[1:-1])
    ELA_AA = int(finalmulti / superf_total) ##+ interval
    
    # Optimized AABR Calculation
    refinf = minalt
    while True:
        # Vectorized calculation
        diff = list_altitudes[1:-1] - refinf
        weighted = resta * diff
        adjusted = np.where(weighted < 0, weighted * AABRratio, weighted)
        total = np.sum(adjusted)
        
        if total <= 0:
            break
        refinf += interval
    
    ELA_AABR = refinf - (interval/2) ##+ interval
    
    return ELA_AA, ELA_AABR
    
##main program
InputPGIPolygons = arcpy.GetParameterAsText(0)
GlaStage = arcpy.GetParameterAsText(1)
RecMethod = arcpy.GetParameterAsText(2)
IceSurf = arcpy.GetParameterAsText(3)
IceTck = arcpy.GetParameterAsText(4)  ##ice surface DEM

interval = int(arcpy.GetParameter(5))
AARratio = arcpy.GetParameter(6)
AABRratio =arcpy.GetParameter(7)

#Add the output 
OutputPGIoutlines = arcpy.GetParameterAsText(8)

arcpy.Delete_management("temp_workspace")

##Copy the input to output polygon
arcpy.CopyFeatures_management(InputPGIPolygons, OutputPGIoutlines)

exist_fields = [f.name for f in arcpy.ListFields(OutputPGIoutlines)] #List of current field names in outline layer
IDName = "PGI_ID"

b_PGI_ID = False
if IDName not in exist_fields:
    #arcpy.AddMessage("The PGI ID does not exist! Will create one with the default ID start with PGI_LGM_ ")
    arcpy.AddField_management(OutputPGIoutlines, IDName, "TEXT") #field for ice value
    b_PGI_ID = True

if "RecMethod" in exist_fields:
    pass
else:
    arcpy.AddField_management(OutputPGIoutlines, "RecMethod", 'Text')

if "A3D" in exist_fields:
    pass
else:
    arcpy.AddField_management(OutputPGIoutlines, "A3D", "LONG",10)

if "A3D2D" in exist_fields:
    pass
else:
    arcpy.AddField_management(OutputPGIoutlines, "A3D2D", "DOUBLE", 6, 3)

new_fields = ("Z_min","Z_max", "Z_range", "Z_mean","Z_median","Z_mid") ##All Integer variables count = 6
for field in new_fields:
    if field in exist_fields:
        pass
    else:
        arcpy.AddField_management(OutputPGIoutlines, field, "LONG",10)

new_fields = ("MeanSlope","MeanAspect", "Hypsomax")
for field in new_fields:
    if field in exist_fields:
        pass
    else:
        arcpy.AddField_management(OutputPGIoutlines, field, "DOUBLE", 8, 1)
      

if "HI" in exist_fields:
    pass
else:
    arcpy.AddField_management(OutputPGIoutlines, "HI", "DOUBLE", 6, 3)

new_fields = ("MGE","AAR","AA","AABR")
for field in new_fields:
    if field in exist_fields:
        pass
    else:
        arcpy.AddField_management(OutputPGIoutlines, field, "LONG",10)        

new_fields = ("MeanTck", "StdTck", "MedianTck", "MaxTck") 
for field in new_fields:
    if field in exist_fields:
        pass
    else:
        arcpy.AddField_management(OutputPGIoutlines, field, "FLOAT",10, 1)

if "Vol_km3" in exist_fields:
    pass
else:
    arcpy.AddField_management(OutputPGIoutlines, "Vol_km3", "FLOAT", 10, 4)

##Add elevation fields
if "PolyID" in exist_fields:
    pass
else:
    arcpy.AddField_management(OutputPGIoutlines, 'PolyID', 'Long', 6)

arcpy.CalculateField_management(OutputPGIoutlines,"PolyID",str("!"+str(arcpy.Describe(OutputPGIoutlines).OIDFieldName)+"!"),"PYTHON_9.3")


arcpy.AddMessage("Step 1: Add glacier surface elevation-related attributes...")
zonalSAT = arcpy.env.scratchGDB + "\\zonalSAT"
ZonalStatisticsAsTable(OutputPGIoutlines, "PolyID", Raster(IceSurf),  zonalSAT, "#", "ALL")
fieldList = ["Min", "Max", "Mean", "Median"]
arcpy.JoinField_management(OutputPGIoutlines, 'PolyID', zonalSAT, 'PolyID', fieldList)
##Add the attributes to the PGIpolugons
fields = ["Z_min","Z_max", "Z_range", "Z_mean","Z_median","Z_mid", "Min", "Max", "Mean", "Median", "RecMethod"]
with arcpy.da.UpdateCursor(OutputPGIoutlines,fields) as cursor:   #populate ice field with value from the nearest flowline point
    for row in cursor:
        row[0]= row[6]
        row[1] = row[7]
        row[2] = row[7] - row[6]
        row[3] = row[8]
        row[4] = row[9]
        row[5] = (row[7] + row[6]) / 2
        row[10] = RecMethod
        cursor.updateRow(row)
del row, cursor

arcpy.DeleteField_management(OutputPGIoutlines,["Min", "Max", "Mean", "Median"])
arcpy.Delete_management(temp_workspace + "\\zonalSAT")

##Check if the PGIIG needs to be added
poly_points = temp_workspace + "\\poly_points"
poly_points_GCS = temp_workspace + "\\poly_points_GCS"
arcpy.FeatureToPoint_management (OutputPGIoutlines, poly_points, "INSIDE")
spatial_ref = arcpy.Describe(poly_points).spatialReference
    
if "GCS" in spatial_ref.name:
    arcpy.CopyFeatures_management(poly_points, poly_points_GCS)
else:
    #arcpy.AddMessage("The DEM projection is not GCS. Re-project!")
    out_coordinate_system = arcpy.SpatialReference("GCS_WGS_1984")
    arcpy.Project_management(poly_points, poly_points_GCS, out_coordinate_system)

arcpy.AddXY_management(poly_points_GCS)

arcpy.AddMessage("Add PGI_ID...")
polys_spatialjoin = temp_workspace + "\\polys_spatialjoin"
arcpy.SpatialJoin_analysis(OutputPGIoutlines, poly_points_GCS, polys_spatialjoin, "JOIN_ONE_TO_ONE", "KEEP_ALL", '#', "COMPLETELY_CONTAINS")
polyarray = arcpy.da.FeatureClassToNumPyArray(polys_spatialjoin, ('Point_X', 'Point_Y'))  
pnt_x = np.array([item[0] for item in polyarray])
pnt_y = np.array([item[1] for item in polyarray])
ids = []
for i in range(len(pnt_x)):
    long_str = str(pnt_x[i])
    dot = long_str.find(".")
    endpos = dot + 4
    if pnt_x[i] < 0:
        ext_str = long_str[1:endpos]
        if len(ext_str) < 6:
            ext_str = "0" + ext_str
        x_str = ext_str + "W"       
    else:
        ext_str = long_str[0:endpos]
        if len(ext_str) < 6:
            ext_str = "0" + ext_str
        x_str = ext_str + "E"       

    lat_str = str(pnt_y[i])
    dot = lat_str.find(".")
    endpos = dot + 4
    if pnt_y[i] < 0:
        ext_str = lat_str[1:endpos]
        if len(ext_str) < 6:
            ext_str = "0" + ext_str
        y_str = ext_str + "S"       
    else:
        ext_str = lat_str[0:endpos]
        if len(ext_str) < 6:
            ext_str = "0" + ext_str
        y_str = ext_str + "N"       

    ##Combine str
    ids.append(x_str+y_str)

##Add the attributes to the PGIpolugons
Prefix = "PGI_" + GlaStage + "_"
fields = [IDName]
with arcpy.da.UpdateCursor(OutputPGIoutlines,fields) as cursor:   #populate ice field with value from the nearest flowline point
    i = 0
    for row in cursor:
        row[0] = Prefix + ids[i]
        #row[1] = RecMethod
        cursor.updateRow(row)
        i += 1
del row, cursor

arcpy.AddMessage("Step 2: Add slope and aspect-related attrbutes...")

DEM_slope = Slope(IceSurf)  
DEM_aspect = Aspect(IceSurf)

##Use zonalstatistics to get the meanslope and meanaspect
outZSaT = ZonalStatisticsAsTable(OutputPGIoutlines, 'PolyID', DEM_slope, temp_workspace + "\\zonalSAT", "#", "MEAN")
arcpy.JoinField_management(OutputPGIoutlines, 'PolyID', temp_workspace + "\\zonalSAT", 'PolyID', "Mean")
##Add the attributes to the PGIpolugons
fields = ["MeanSlope", "Mean"]
with arcpy.da.UpdateCursor(OutputPGIoutlines,fields) as cursor:   #populate ice field with value from the nearest flowline point
    for row in cursor:
        row[0]= round(row[1],1)
        cursor.updateRow(row)
del row, cursor
arcpy.DeleteField_management(OutputPGIoutlines,["Mean"])
arcpy.Delete_management(temp_workspace + "\\zonalSAT")

outZSaT = ZonalStatisticsAsTable(OutputPGIoutlines, 'PolyID', DEM_aspect, temp_workspace + "\\zonalASP", "#", "MEAN", "#", "#", "#", "CIRCULAR") ##use circular statistics for aspect
arcpy.JoinField_management(OutputPGIoutlines, 'PolyID', temp_workspace + "\\zonalASP", 'PolyID', "C_MEAN")


##Add the attributes to the PGIpolugons
fields = ["MeanAspect", "C_MEAN"]
with arcpy.da.UpdateCursor(OutputPGIoutlines,fields) as cursor:   #populate ice field with value from the nearest flowline point
    for row in cursor:
        row[0]= round(row[1], 1)
        cursor.updateRow(row)
del row, cursor
arcpy.DeleteField_management(OutputPGIoutlines,["C_MEAN"])
arcpy.Delete_management(temp_workspace + "\\zonalASP")

arcpy.AddMessage("Step 3: Add Hypsomax, HI, 3D, and recontructed ELA...")

FcID = arcpy.Describe(OutputPGIoutlines).OIDFieldName
fields = (FcID, "SHAPE@","MGE","AAR","AA","AABR", "HI", "Hypsomax", "A3D2D", "A3D", "SHAPE@AREA")

volumetable = arcpy.env.scratchFolder + "\\volumetable.txt"
    

with arcpy.da.UpdateCursor(OutputPGIoutlines, fields) as cursor:
    for row in cursor:
        gid = row[0]
        arcpy.AddMessage("Processing Glacier #" + str(gid))

        galcierDEM = ExtractByMask(IceSurf, row[1])

        array = arcpy.RasterToNumPyArray(galcierDEM,"","","",0)
        EleArr = array[array > 0].astype(int) ##Get the elevations greater than zero
        try:
            ela_aar, ela_mge = ELA_AAR_MGE(EleArr, interval, AARratio)
            row[2] = ela_mge
            row[3] = ela_aar
            ela_aa, ela_AABR = ELA_AA_AABR(EleArr, interval, AABRratio)
            row[4] = ela_aa
            row[5] = ela_AABR

            ##Calcualte the Hypsometric max and Hypsometric intergal
            Z_min = np.min(EleArr)
            Z_max = np.max(EleArr)
            Z_mean = np.mean(EleArr)

            Hi = (Z_mean - Z_min) / (Z_max - Z_min)
            row[6] = round(Hi,3)
            
            vals,counts = np.unique(EleArr, return_counts=True)
            index = np.argmax(counts)
            hypo_max = vals[index]
            row[7] = hypo_max
            
            #calculate 3D surface
            ##Step 1: Conduct Suface Volume analysis to generate the surface volume table, volumetable
            if arcpy.Exists(volumetable):
                arcpy.Delete_management(volumetable)
            
            arcpy.SurfaceVolume_3d(galcierDEM, volumetable, "ABOVE", "0")
            ##Step 2: Read the volume table for 3D area and 2Darea, and calculate the A3D/A2D ratio
            arr=arcpy.da.TableToNumPyArray(volumetable, ('AREA_2D', 'AREA_3D'))
            area_2D = float(arr[0][0])
            area_3D = float(arr[0][1])
            Ratio3D2D = area_3D / area_2D
            ##Step 3: Assign the values to the attibute fields
            row[8] = round(Ratio3D2D, 3)
            ##Step 4: make sure to delete volumetable, so that it only has one record for the corresponding cirque outline
            arcpy.Delete_management(volumetable)

            #Adjust Area3D based on the A3D/A2D ratio and vector A2D to be consistent with the ratio
            A2D = row[10]
            adjusted_area_3D = A2D * Ratio3D2D
            row[9] = adjusted_area_3D
        except:
            arcpy.AddMessage("No ice surface info are related to the outline")
            row[4] = -999
            row[5] = -999
            row[6] = -999
            row[7] = -999
            row[8] = -999
            row[9] = -999
        
        cursor.updateRow(row)

del row, cursor

arcpy.AddMessage("Step 4: Add ice thickness-related attributes...")
outZSaT = ZonalStatisticsAsTable(OutputPGIoutlines, 'PolyID', Raster(IceTck), temp_workspace + "\\zonalSAT", "#", "ALL")
fieldList = ["Mean", "STD", "Median", "Max"]
arcpy.JoinField_management(OutputPGIoutlines, 'PolyID', temp_workspace + "\\zonalSAT", 'PolyID', fieldList)
##Add the attributes to the PGIpolugons
fields = ["MeanTck", "StdTck", "MedianTck", "MaxTck", "Vol_km3", "Mean", "STD", "Median", "Max", "SHAPE@AREA"]
with arcpy.da.UpdateCursor(OutputPGIoutlines,fields) as cursor:   #populate ice field with value from the nearest flowline point
    for row in cursor:
        row[0]= round(row[5],1)  ##mean
        row[1] = round(row[6],1) ##std
        row[2] = round(row[7],1) ##median
        row[3] = round(row[8],1) ##max
        row[4] = round((row[9] * row[5]) / 1e9, 4) ##volume km3
        cursor.updateRow(row)
del row, cursor

arcpy.DeleteField_management(OutputPGIoutlines,["Mean", "STD", "Median", "Max"])
arcpy.DeleteField_management(OutputPGIoutlines,["PolyID"])

arcpy.AddMessage("Finished!!!")
arcpy.Delete_management("temp_workspace")

