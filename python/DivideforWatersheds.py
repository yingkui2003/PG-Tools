#-------------------------------------------------------------------------------
# Name: DivideforWatersheds.py
# Purpose: This tool divides paleoglacier or modern glacier polygon outlines based on
# watershed (catchment or drainage basin) boundaries
#
# Created:     03/04/2023 - 03/08/2023
# Author: Dr. Yingkui Li
# Department of Geography, University of Tennessee
# Knoxville, TN 37996
#-------------------------------------------------------------------------------
# Import arcpy module
import arcpy, sys
from arcpy import env
from arcpy.sa import *
import numpy as np
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
    except:
        raise Exception ("unable to check out extension")
    try:
        if arcpy.CheckExtension("3D")=="Available":
            arcpy.CheckOutExtension("3D")
        else:
            raise Exception ("not extension available")
    except:
        raise Exception ("unable to check out extension")
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
InputDEM = arcpy.GetParameterAsText(0)
InputOutlines = arcpy.GetParameterAsText(1)
Min_Ele_Range = arcpy.GetParameter(2)
OutputIndividualOutlines = arcpy.GetParameterAsText(3)

##Clean up the temp_workspace
arcpy.Delete_management(temp_workspace)
#spatialref=arcpy.Describe(InputDEM).spatialReference
cellsize = arcpy.GetRasterProperties_management(InputDEM,"CELLSIZEX")
cellsize_int = int(float(cellsize.getOutput(0)))
min_area = 5 *  cellsize_int * cellsize_int ##set the min_area as 5 cell sizes of the DEM

##Step 1: clip DEM based on the buffer of oulines 
arcpy.AddMessage("Step 1: Extract DEM for glacier outlines...")
##Do a loop for each outline polygon
outline_buf = temp_workspace + "\\outline_buf"
dissove_buf = temp_workspace + "\\dissove_buf"
buffer_dis = str(cellsize_int*10) + " Meters"  ##use the 10 times of cell size for the buffer distance
arcpy.Buffer_analysis(InputOutlines, outline_buf, buffer_dis)
arcpy.Dissolve_management(outline_buf, dissove_buf, "", "", "SINGLE_PART")
##Extract DEM
extractDEM = ExtractByMask(InputDEM, dissove_buf)

###Step 2: Basin analysis
arcpy.AddMessage("Step 2: Extract catchments for glacier outlines...")

##set the parallelProcessingFactor for large DEMs
dem = Raster(extractDEM)
nrow = extractDEM.height
ncol = extractDEM.width

oldPPF = arcpy.env.parallelProcessingFactor
if (nrow > 1500 or ncol > 1500):
    arcpy.AddMessage("The DEM has " +str(nrow) + " rows and " + str(ncol) + " columns")
    arcpy.env.parallelProcessingFactor = 0 ##use 0 for large rasters
    
#Hydro analysis
fillDEM =Fill(extractDEM)  ##Fill the sink first
fdir = FlowDirection(fillDEM, "FORCE") ##Flow direction force out edge
outBasin = Basin(fdir)

#Extract the outbasin within the input outlines
extBasin = ExtractByMask(outBasin, InputOutlines)

##Convert Raster to Polygon
arcpy.RasterToPolygon_conversion(extBasin, temp_workspace + "\\divided_polys", "SIMPLIFY", "VALUE", "SINGLE_OUTER_PART")


##Merge the polygons based on the elevation range of the polygon
arcpy.AddMessage("Step 3: Merge small_relief polygons to nearby large polygons...")
arcpy.AddField_management(temp_workspace + "\\divided_polys", 'MergeID', 'Long', 6) 
arcpy.AddField_management(temp_workspace + "\\divided_polys", 'AREA', 'Long', 10)
arcpy.CalculateField_management(temp_workspace + "\\divided_polys","MergeID",str("!"+str(arcpy.Describe(temp_workspace + "\\divided_polys").OIDFieldName)+"!"),"PYTHON_9.3")

##Add the Area attribute
with arcpy.da.UpdateCursor(temp_workspace + "\\divided_polys",("SHAPE@AREA", "AREA")) as cursor:   #populate ice field with value from the nearest flowline point
    for row in cursor:
        row[1] = row[0]
        cursor.updateRow(row)
del row, cursor

##Extract the elevation range for the polygons based on Zonal ststistics
#outZonalStatistics = ZonalStatistics(temp_workspace + "\\divided_polys", 'MergeID', fillDEM, "RANGE")
outZSaT = ZonalStatisticsAsTable(temp_workspace + "\\divided_polys", 'MergeID', fillDEM, temp_workspace + "\\zonalDEM", "#", "ALL")
fieldList = ["Range", "Mean"]
arcpy.JoinField_management(temp_workspace + "\\divided_polys", 'MergeID', temp_workspace + "\\zonalDEM", 'MergeID', fieldList)
#arcpy.CopyFeatures_management(temp_workspace + "\\divided_polys", "c:\\test\\divided_polys.shp")

small_relief_polygons = temp_workspace + "\\small_relief_polygons"
large_relief_polygons = temp_workspace + "\\large_relief_polygons"
min_relief = float(Min_Ele_Range)
query = "( Range < " + str(min_relief) + ") or (AREA < " + str(min_area) + ")" 
#arcpy.AddMessage(query)
arcpy.Select_analysis (temp_workspace + "\\divided_polys", small_relief_polygons, query)
polyArray = arcpy.da.FeatureClassToNumPyArray(small_relief_polygons, "OID@")
arcpy.AddMessage("The number of merged small relief polygons is " + str(len(polyArray)))
if len(polyArray)> 0: ## if there are small polygons
    bLoop = True
    start_n = len(polyArray)
    while bLoop:
        arcpy.Erase_analysis(temp_workspace + "\\divided_polys", small_relief_polygons, large_relief_polygons)
        
        arcpy.SpatialJoin_analysis(small_relief_polygons, large_relief_polygons, temp_workspace + "\\small_polygons_spatialjoin", "JOIN_ONE_TO_ONE", "KEEP_ALL", '#', "INTERSECT", "1 Meters", "#")
        with arcpy.da.UpdateCursor(temp_workspace + "\\small_polygons_spatialjoin",("MergeID", "MergeID_1")) as cursor:   #populate ice field with value from the nearest flowline point
            for row in cursor:
                row[0]=row[1]
                cursor.updateRow(row)
        del row, cursor
        arcpy.Append_management(temp_workspace + "\\small_polygons_spatialjoin", large_relief_polygons, "NO_TEST")
        arcpy.Dissolve_management(large_relief_polygons, temp_workspace + "\\divided_polys", "MergeID")
        
        arcpy.Select_analysis (temp_workspace + "\\divided_polys", temp_workspace + "\\Null_polygons", "MergeID IS NULL")
        arcpy.MultipartToSinglepart_management(temp_workspace + "\\Null_polygons", small_relief_polygons)
        polyArray2 = arcpy.da.FeatureClassToNumPyArray(small_relief_polygons, "OID@")
        arcpy.AddMessage("The number of small relief polygons left is " + str(len(polyArray2)))
        
        if ((len(polyArray2) == 0) or (len(polyArray2) == start_n)):
            break
        start_n = len(polyArray2)
                      
    arcpy.DeleteField_management(temp_workspace + "\\divided_polys",["MergeID"])

    
arcpy.MultipartToSinglepart_management(temp_workspace + "\\divided_polys", temp_workspace + "\\divided_polys_singlePart")
##Delete small polygons caused by the conversion
with arcpy.da.UpdateCursor(temp_workspace + "\\divided_polys_singlePart",("SHAPE@AREA")) as cursor:   #populate ice field with value from the nearest flowline point
    for row in cursor:
        if row[0] < min_area: ##delete the small polygon generated by the conversions
            #arcpy.AddMessage("delete small polygon")
            cursor.deleteRow()
del row, cursor

##Make sure to transfer the old attributes to the divided polygons
final_outlines = temp_workspace + "\\final_outlines"
arcpy.SpatialJoin_analysis(temp_workspace + "\\divided_polys_singlePart", InputOutlines, OutputIndividualOutlines, "JOIN_ONE_TO_ONE", "KEEP_COMMON", '#', "INTERSECT", "1 Meters", "#")

max_gap_area = str(min_area) + " SquareMeters"
try:
    arcpy.topographic.FillGaps(OutputIndividualOutlines, max_gap_area)
except:
    pass
arcpy.DeleteField_management(OutputIndividualOutlines,["Join_Count", "TARGET_FID", "ORIG_FID"])

arcpy.AddMessage("Finished!!!")
arcpy.Delete_management("temp_workspace")
##Reset parallelProcessingFactor to the default
arcpy.env.parallelProcessingFactor = oldPPF
