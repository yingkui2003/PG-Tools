#-------------------------------------------------------------------------------
# Name: AddBasicGlacierAttributes.py
# Purpose: This tool adds the basic paleoglacier attributes.
#          The inputs of this tool include the divided glacier outlines,
#          the glacial stage of the outline, an (optional) age point file, and the age field name,
#          and the ICED SiteID if the age point file is derived from the ICE-D dataset.
#          This tool first generates a PGI_ID based on the glacial stage and the latitude and longitude
#          of the centroid of each outline (polygon) and then derive attributes. If the age point file
#          is provided, the tool will also generate the age-related attributes. 
#
# Author:    Yingkui Li
# Created:   03/04/2023-02/21/2025
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
    
##main program
InputPGIPolygons = arcpy.GetParameterAsText(0)
Stage = arcpy.GetParameterAsText(1)
InputAgeFile = arcpy.GetParameterAsText(2)
InputDatingMethod = arcpy.GetParameterAsText(3)
InputAgeField = arcpy.GetParameterAsText(4)
InputICEDsite = arcpy.GetParameterAsText(5)
#Add the output 
OutputPGIoutlines = arcpy.GetParameterAsText(6)

arcpy.Delete_management(temp_workspace)



##Copy the input to output polygon
arcpy.CopyFeatures_management(InputPGIPolygons, OutputPGIoutlines)

exist_fields = [f.name for f in arcpy.ListFields(OutputPGIoutlines)] #List of current field names in outline layer
IDName = "PGI_ID"

if IDName not in exist_fields:
    arcpy.AddField_management(OutputPGIoutlines, IDName, "TEXT") #field for ice value

new_fields = ("Valley","Range", "Region", "Mapper", "MapDate", "Reviewer", "DataSource", "URL", "MapMethod", "Desc", "GlaStage") ##All double variables count = 4
for field in new_fields:
    if field in exist_fields:
        pass
    else:
        arcpy.AddField_management(OutputPGIoutlines, field, "TEXT")

##Add new fields
new_fields = ("Cenlon","Cenlat") ##All double variables count = 4
for field in new_fields:
    if field in exist_fields:
        pass
    else:
        arcpy.AddField_management(OutputPGIoutlines, field, "DOUBLE",10, 4)

new_fields = ("PolyID","Perimeter", "A2D") ##All Integer variables count = 7
for field in new_fields:
    if field in exist_fields:
        pass
    else:
        arcpy.AddField_management(OutputPGIoutlines, field, "LONG",10)

arcpy.CalculateField_management(OutputPGIoutlines,"PolyID",str("!"+str(arcpy.Describe(OutputPGIoutlines).OIDFieldName)+"!"),"PYTHON_9.3")


new_fields = ("MinAge", "MaxAge", "MedianAge", "MeanAge") ##All Integer variables count = 7
for field in new_fields:
    if field in exist_fields:
        pass
    else:
        arcpy.AddField_management(OutputPGIoutlines, field, "DOUBLE", 10, 2)

new_fields = ("AgeMethod","ICEDSiteID") ##All Integer variables count = 6
for field in new_fields:
    if field in exist_fields:
        pass
    else:
        arcpy.AddField_management(OutputPGIoutlines, field, "TEXT")

##Create PGI_ID and add centriold lat and long
poly_points = temp_workspace + "\\poly_points"
poly_points_GCS = temp_workspace + "\\poly_points_GCS"

arcpy.FeatureToPoint_management (OutputPGIoutlines, poly_points, "INSIDE")

spatial_ref = arcpy.Describe(poly_points).spatialReference

if "GCS" in spatial_ref.name:
    arcpy.CopyFeatures_management(poly_points, poly_points_GCS)
else:
    out_coordinate_system = arcpy.SpatialReference("GCS_WGS_1984")
    arcpy.Project_management(poly_points, poly_points_GCS, out_coordinate_system)

arcpy.AddXY_management(poly_points_GCS)

arcpy.AddMessage("Add PGI_ID, centroid location, perimeter, and area...")
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
fields = [IDName, "Cenlon","Cenlat", "Perimeter", "A2D", "SHAPE@LENGTH", "SHAPE@AREA", "GlaStage"]
Prefix = "PGI_" + Stage + "_"
with arcpy.da.UpdateCursor(OutputPGIoutlines,fields) as cursor:   #populate ice field with value from the nearest flowline point
    i = 0
    for row in cursor:
        row[0]= Prefix + ids[i]
        row[1] = round(pnt_x[i], 4)
        row[2] = round(pnt_y[i], 4)
        row[3] = row[5]
        row[4] = row[6]
        row[7] = Stage
        cursor.updateRow(row)
        i += 1
del row, cursor

##Add elevation fields
if InputAgeFile != "": ##get the average age from the age point file
    arcpy.AddMessage("Add outline ages...")
    #This is the prcoess to get the average age from the age file
    if InputAgeField != "":
        ages_spatialjoin = temp_workspace + "\\ages_spatialjoin"
        arcpy.SpatialJoin_analysis(InputAgeFile, OutputPGIoutlines, ages_spatialjoin, "JOIN_ONE_TO_ONE", "KEEP_COMMON", '#', "WITHIN_A_DISTANCE", "150 Meters")

        #poly_IDs  = []
        min_ages    = []
        max_ages    = []
        median_ages = []
        mean_ages   = []
        icedsites   = []

        if InputICEDsite != "":
            fields = ('PolyID', InputAgeField, InputICEDsite)
        else:
            fields = ('PolyID', InputAgeField)
            
        age_array = arcpy.da.FeatureClassToNumPyArray(ages_spatialjoin, fields)
        polyIDs = np.array([item[0] for item in age_array])
        ages    = np.array([item[1] for item in age_array])
        if InputICEDsite != "":
            sites   = np.array([item[2] for item in age_array])

        unique_polyIDs = np.unique(polyIDs)
        for polyID in unique_polyIDs:
            ##Need to select the ages from the same site id
            if InputICEDsite != "":
                outline_ages = ages[polyIDs == polyID]
                site_IDs = sites[polyIDs == polyID]
                unique_siteIDs, counts = np.unique(site_IDs, return_counts=True)

                max_count = max(counts)
                site_ID = unique_siteIDs[counts == max_count][0]

                icedsites.append(site_ID)
                
                sel_ages = outline_ages[site_IDs == site_ID]
            else:
                icedsites.append("NULL")
                sel_ages = ages[polyIDs == polyID]

            min_ages.append(np.min(sel_ages))
            max_ages.append(np.max(sel_ages))
            median_ages.append(np.median(sel_ages))
            mean_ages.append(np.mean(sel_ages))

        fields = ["PolyID", "MinAge", "MaxAge", "MedianAge", "MeanAge", "ICEDSiteID", "AgeMethod"]
        with arcpy.da.UpdateCursor(OutputPGIoutlines,fields) as cursor:   #populate ice field with value from the nearest flowline point
            for row in cursor:
                idx_result = np.where(unique_polyIDs == row[0])
                if len(idx_result[0])> 0:
                    idx = idx_result[0][0]
                    row[1] = min_ages[idx]
                    row[2] = max_ages[idx]
                    row[3] = median_ages[idx]
                    row[4] = mean_ages[idx]
                    row[5] = icedsites[idx]
                    row[6] = InputDatingMethod
                cursor.updateRow(row)
        del row, cursor

    else:
        arcpy.AddMessage("No age field is selected")
        
arcpy.DeleteField_management(OutputPGIoutlines,["PolyID"])
arcpy.Delete_management(temp_workspace)

arcpy.AddMessage("Finished!!!")
