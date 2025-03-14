#-------------------------------------------------------------------------------
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

def ELA_AAR_MGE(EleArr, interval, ratio):
    minimum = np.min(EleArr)
    maximum = np.max(EleArr)

    maxalt=int(maximum+interval)
    minalt=int(minimum-interval)

    # Create list of altitudes and populate primervalor
    Elelist = range(minalt, maxalt, interval)

    H,X1 = np.histogram( EleArr, bins = Elelist, density = True )
    dx = X1[1] - X1[0]
    Area3D_arr = np.cumsum(H)*dx
    
    superf_total=max(Area3D_arr) # Get the total surface
    Area3D_arr = superf_total - Area3D_arr

    ELA=superf_total * ratio # Get the surface above the ELA
    kurowski= superf_total * 0.5

    # Create a list of the altitudes whose surface is less than ELA
    superf_en_ELA=[]
    superf_kurowski=[]
    for values in Area3D_arr:
        if values <= ELA and values<= kurowski:
            superf_en_ELA.append(values)
            superf_kurowski.append(values)
        elif values <= ELA and values> kurowski:
            superf_en_ELA.append(values)
        elif values > ELA and values<= kurowski:
            superf_kurowski.append(values)
        else:
            pass

    # Get the maximum surface value within the list
    ela=max(superf_en_ELA)
    kur=max(superf_kurowski)

    idx_result = np.where(Area3D_arr == ela)
    idx = idx_result[0][0]
    ELA_AAR=Elelist[idx]+(interval/2) + interval ##Add one interval to match the old AA value by Yingkui 10/08/2023

    idx_result = np.where(Area3D_arr == kur)
    idx = idx_result[0][0]
    ELA_MGE=Elelist[idx]+(interval/2) + interval ##Add one interval to match the old AA value
    
    return ELA_AAR, ELA_MGE 

def ELA_AA_AABR(EleArr, interval, ratio):
    minimum = np.min(EleArr)
    maximum = np.max(EleArr)
   
    maxalt=int(maximum+interval)
    minalt=int(minimum-interval)

    # Create a list of altitudes
    list_altitudes=[]
    start_altitude=minalt+(interval/2)
    while start_altitude > minalt and start_altitude < maxalt:
        list_altitudes.append(start_altitude)
        start_altitude=start_altitude+interval

    Elelist = range(minalt, maxalt, interval)
    
    H,X1 = np.histogram( EleArr, bins = Elelist, density = True )
    dx = X1[1] - X1[0]
    Area3D_arr = np.cumsum(H)*dx*100 ##times 100 to get the percentage

    # AA Calculation
    superf_total=max(Area3D_arr) # Get the total surface

    resta=[int(x)-int(y) for (x,y) in zip(Area3D_arr[1:], Area3D_arr[0:])]

    multiplicacion=[int(x)*int (y) for (x,y) in zip (resta,list_altitudes)]

    finalmulti=sum(multiplicacion)

    ELA_AA=int(int(finalmulti)/int(superf_total)) + interval ##Add one interval to match the old AA value

    # AABR Calculation
    refinf=minalt
    valores_multi=[]
    valorAABR=[x*(y - refinf) for (x,y) in zip (resta, list_altitudes)]
    
    for valoracion in valorAABR:
        if valoracion<0:
            valores_multi.append(int (valoracion*ratio))
        else:
            valores_multi.append(int (valoracion))

    valorAABRfinal=sum (valores_multi)

    while valorAABRfinal > 0:
        refinf = refinf + interval
        valores_multi=[]
        valorAABR=[x*(y - refinf) for (x,y) in zip (resta, list_altitudes)]

        for valoracion in valorAABR:
            if valoracion < 0:
                valores_multi.append(valoracion*ratio)
            else:
                valores_multi.append(valoracion)

        valorAABRfinal=sum (valores_multi)

    ELA_AABR = refinf-(interval/2) + interval ##Add one interval to match the old AA value
    
    return ELA_AA, ELA_AABR 
    
##main program
InputPGIPolygons = arcpy.GetParameterAsText(0)
RecMethod = arcpy.GetParameterAsText(1)
IceSurf = arcpy.GetParameterAsText(2)
IceTck = arcpy.GetParameterAsText(3)  ##ice surface DEM

interval = int(arcpy.GetParameter(4))
AARratio = arcpy.GetParameter(5)
AABRratio =arcpy.GetParameter(6)

#Add the output 
OutputPGIoutlines = arcpy.GetParameterAsText(7)

arcpy.Delete_management("temp_workspace")

##Copy the input to output polygon
arcpy.CopyFeatures_management(InputPGIPolygons, OutputPGIoutlines)

exist_fields = [f.name for f in arcpy.ListFields(OutputPGIoutlines)] #List of current field names in outline layer
IDName = "PGI_ID"

b_PGI_ID = False
if IDName not in exist_fields:
    arcpy.AddMessage("The PGI ID does not exist! Will create one with the default ID start with PGI_LGM_ ")
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
if b_PGI_ID:
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
    Prefix = "PGI_LGM_" ##Need a parameter to set this up
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

