##
##
import os
import arcpy
import numpy as np
import matplotlib.pylab as plt
from matplotlib.backends.backend_pdf import PdfPages
import scipy.optimize as optimize

##############################################################################
## define functions
##---------------------------------------------------------------------------
def false_hillshade(dH_matrix,myext,mytitle):
#    pp = PdfPages('multipage.pdf')
    fig=plt.figure(figsize=(7,7))
    im1 = plt.imshow(dH_matrix,extent=myext)
    im1.set_clim(-20,20)
    im1.set_cmap('Greys')
    fig.suptitle(mytitle,fontsize=14)
    plt.annotate('MEAN:    %.1f m' % np.nanmean(dH_matrix), xy=(0.65, 0.11), xycoords='axes fraction', fontsize=12, fontweight='bold',color='red')
    plt.annotate('MEDIAN: %.1f  m' % np.median(dH_matrix), xy=(0.65, 0.06), xycoords='axes fraction',fontsize=12, fontweight='bold',color='red')
    plt.annotate('STD:         %.1f  m' % np.nanstd(dH_matrix), xy=(0.65, 0.01), xycoords='axes fraction', fontsize=12, fontweight='bold',color='red')
    plt.colorbar(im1,fraction=0.046, pad=0.04)
    plt.tight_layout()
    pp.savefig(fig)
    return
##---------------------------------------------------------------------------
def preprocess(outmask1,outmask2,slope_raster,aspect_raster,masterDEM_raster,slaveDEM_raster):
    ## CONVERT RASTERS TO NUMPY ARRAYS FOR CALCULATIONS
    mymask1_matrix = arcpy.RasterToNumPyArray(outmask1)
    mymask2_matrix = arcpy.RasterToNumPyArray(outmask2)

    slope_matrix = arcpy.RasterToNumPyArray(slope_raster)
    aspect_matrix = arcpy.RasterToNumPyArray(aspect_raster)
    stan_matrix = np.tan(np.radians(slope_matrix))

    # DIFFERENCE DEMS
    dH = (masterDEM_raster) - (slaveDEM_raster)
    dH_matrix = arcpy.RasterToNumPyArray(dH)
    dH_matrix = dH_matrix.astype(float)
    dHtan_matrix = dH_matrix/stan_matrix

    #############################################################################
    ## SELECTION and initional plotting
    mykeep = ((np.absolute(dH_matrix)< 25) & (mymask1_matrix!=1) & (mymask2_matrix==1) & (slope_matrix > 5) & (dH_matrix != 0) & (aspect_matrix>=0))
    dH_matrix[np.invert(mykeep)]=(np.nan)
    ## CREATE NEW VECTORS CONTAINING SAMPLE -
    xdata = aspect_matrix[mykeep]
    ydata = dHtan_matrix[mykeep]
    sdata = stan_matrix[mykeep]
    return dH_matrix,dH,xdata,ydata,sdata
##---------------------------------------------------------------------------
def coreg_fitting(xdata,ydata,sdata,mytitle2):
    xdata = xdata.astype(np.float64)
    ydata = ydata.astype(np.float64)
    sdata = sdata.astype(np.float64)
    # Fit using equation 3 of Nuth and Kääb, 2011
    fitfunc = lambda p, x: p[0]*np.cos(np.radians(p[1]-x))+p[2]# Target function
    errfunc = lambda p, x, y: (fitfunc(p, x) - y) # Distan_matrixce to the target function
    p0 = [-1, 1, -1]
    p1, success = optimize.leastsq(errfunc, p0[:], args=(xdata, ydata))
    print (success)
    print (p1)
    # Convert to shift parameters in cartesian coordinates
    xadj = p1[0] * np.sin(np.radians(p1[1]))
    yadj = p1[0] * np.cos(np.radians(p1[1]))
    zadj = p1[2] * sdata.mean(axis=0)

    xp = np.linspace(0,360,361)
    yp = fitfunc(p1,xp)

    if xdata.size>50000:
        mysamp = np.random.randint(0,xdata.size,50000)
    else:
        mysamp = np.arange(0,xdata.size)

    fig = plt.figure(figsize = (7,4), dpi = 600)
    fig.suptitle(mytitle2,fontsize=14)
#    plt.plot(xdata[mysamp], ydata[mysamp], 'b.', ms=1.0)
#    plt.plot(xp,np.zeros(xp.size),'k',ms=3)
#    plt.plot(xp,yp,'r-', ms = 2)
    plt.plot(xdata[mysamp], ydata[mysamp], '.', ms=0.5,color='0.5', rasterized=True)
    plt.plot(xp,np.zeros(xp.size),'k',ms=3)
    plt.plot(xp,yp,'r-', ms = 2)

    plt.axis([0, 360, -200, 200])
    plt.xlabel('Aspect [degrees]')
    plt.ylabel('dH / tan(slope)')
    plt.text(20, -125, '$\Delta$x: %.1f meters' % xadj, fontsize=12, fontweight='bold',color='red')
    plt.text(20, -150, '$\Delta$y: %.1f  meters' % yadj, fontsize=12, fontweight='bold',color='red')
    plt.text(20, -175, '$\Delta$z: %.1f  meters' % zadj, fontsize=12, fontweight='bold',color='red')
    pp.savefig(fig, rasterized=True)
    return xadj,yadj,zadj
#############################################################################
## DEFINE input data
#Set script parameter values

##mdemname = arcpy.GetParameterAsText(0)
##sdemname = arcpy.GetParameterAsText(1)
##inshape1 = arcpy.GetParameterAsText(2)
mdemname = r""
sdemname = r""
inshape1 = r""


inshape2 = arcpy.GetParameterAsText(3)
##myworkspace = arcpy.GetParameterAsText(3)
myworkspace = r""

snameorig = sdemname
dHpost = "dHpost_full.tif"
dHpost_sample = "dHpost_sample.tif"
tempshape = "myshape"


pp = PdfPages(myworkspace + '\CoRegistration_Results.pdf')
##############################################################################
# DEFINE WORKSPACE - automatically or as input in tool? The DEMs
arcpy.env.workspace = os.path.join(myworkspace)
arcpy.env.overwriteOutput = True
arcpy.env.parallelProcessingFactor = "50%"

# SET GEOPROCESSING ENVIRONMENT
arcpy.CheckOutExtension("Spatial")
arcpy.env.resample = "BILINEAR"
arcpy.env.extent = "MAXOF"
##############################################################################
## RESAMPLE MASTER DEM TO CELLSIZE OF SLAVE DEM
masterDEM_raster = arcpy.Resample_management(arcpy.sa.SetNull(mdemname,mdemname,"VALUE < -9000"),"mDEM",arcpy.GetRasterProperties_management(sdemname,"CELLSIZEX"),"BILINEAR")
slaveDEM_raster = arcpy.sa.SetNull(sdemname,sdemname,"VALUE < -9000")

arcpy.env.extent = "mDEM"
arcpy.env.snapRaster = "mDEM"
arcpy.env.cellSize = "mDEM"

#############################################################################
# For the exclusion masks
if not inshape1:
    outmask1 = arcpy.sa.CreateConstantRaster(0,"INTEGER")
    outmask1.save("outmask1")
else:
    outshape1 = arcpy.MakeFeatureLayer_management(inshape1,r"in_memory\outshape1")
    arcpy.AddField_management(outshape1,"CORCODE","SHORT")
    arcpy.CalculateField_management(outshape1,"CORCODE",1,"PYTHON_9.3")
    arcpy.PolygonToRaster_conversion(outshape1,"CORCODE","outmask1","CELL_CENTER")
    arcpy.DeleteField_management(outshape1,"CORCODE")
    outmask1 = arcpy.Raster("outmask1")

# FOR THE INCLUSION MASKS
if not inshape2:
    outmask2 = arcpy.sa.CreateConstantRaster(1,"INTEGER")
    outmask2.save("outmask2")
else:
    outshape2 = arcpy.MakeFeatureLayer_management(inshape2,r"in_memory\outshape2")
    arcpy.AddField_management(outshape2,"CORCODE","SHORT")
    arcpy.CalculateField_management(outshape2,"CORCODE",1,"PYTHON_9.3")
    arcpy.PolygonToRaster_conversion(outshape2,"CORCODE","outmask2","CELL_CENTER")
    arcpy.DeleteField_management(outshape2,"CORCODE")
    outmask2 = arcpy.Raster("outmask2")

##############################################################################
#Generate SLOPE and ASPECT from Master DEM
slope_raster = arcpy.sa.Slope("mDEM", "DEGREE")
aspect_raster = arcpy.sa.Aspect("mDEM")

##############################################################################
## WHILE LOOP
mythresh = np.float64(100)
mystd = np.float64(100)
mycount = 0;
tot_dx = np.float64(0)
tot_dy = np.float64(0)
tot_dz = np.float64(0)
magnthresh = 100;
mytitle = "DEM difference: Pre-coregistration"
while mythresh > 1 and magnthresh > 0.5 :
#for ab in range(1,7):
    if mycount !=0:
        sdemname = slaveDEM_adj
        print (sdemname)
        mytitle = "DEM difference: After Iteration %s" % mycount
        arcpy.Delete_management("finalslave%s" % (mycount-1))
        arcpy.env.extent = "mDEM"
        arcpy.env.snapRaster = "mDEM"
        arcpy.env.cellSize = "mDEM"

    mycount = mycount + 1
    print ("Running iteration #%s" % mycount)
    #
    ##############################################################################
    ##Resample slaveDEM to masterDEM
#    arcpy.Resample_management(arcpy.sa.SetNull(sdemname,sdemname,"VALUE < -9000"),r"in_memory/sDEM%s" % mycount,arcpy.GetRasterProperties_management("mDEM","CELLSIZEX"),"BILINEAR")
    arcpy.Resample_management(sdemname,r"in_memory/sDEM%s" % mycount,arcpy.GetRasterProperties_management("mDEM","CELLSIZEX"),"BILINEAR")
    ##############################################################################
    ## Calvulate Difference
    dH_matrix,dH,xdata,ydata,sdata = preprocess(outmask1,outmask2,slope_raster,aspect_raster,arcpy.Raster("mDEM"),arcpy.Raster(r"in_memory/sDEM%s" % mycount))

    myext = np.asarray([dH.extent.lowerLeft.X,dH.extent.upperRight.X,dH.extent.lowerLeft.Y,dH.extent.upperRight.Y])/1000
    false_hillshade(dH_matrix,myext,mytitle)
    mythresh = np.multiply((mystd-np.nanstd(dH_matrix))/mystd,100)
    mystd = np.nanstd(dH_matrix)

    ## RUN FITTING ROUTINE
    mytitle2 = "Co-Registration: Iteration %s" % mycount
    dx,dy,dz = coreg_fitting(xdata,ydata,sdata,mytitle2)
    tot_dx = tot_dx + dx
    tot_dy = tot_dy + dy
    tot_dz = tot_dz + dz
    magnthresh = np.sqrt(np.square(dx)+np.square(dy)+np.square(dz))
    ## RESET ENVIRONMENTS
    arcpy.ResetEnvironments()
    arcpy.env.workspace = os.path.join(myworkspace)
    arcpy.env.overwriteOutput = True
    arcpy.env.parallelProcessingFactor = "50%"
    arcpy.CheckOutExtension("Spatial")
    arcpy.env.resample = "BILINEAR"
    ## SHIFT SLnAVE DEM
    arcpy.Shift_management(slaveDEM_raster, r"in_memory/tempslave%s" % mycount, tot_dx,tot_dy)
    slaveDEM_adj = arcpy.sa.Plus(r"in_memory\tempslave%s" % mycount, tot_dz)
    slaveDEM_adj.save("finalslave%s" % mycount)

    if mythresh > 1 and magnthresh > 0.5 :
        dH_matrix = None
        dx = None
        dy = None
        dz = None
        xdata = None
        ydata = None
        sdata = None
        arcpy.Delete_management("in_memory")
#        arcpy.Delete_management("sDEM")
    else :
       dHFinal = dH
       arcpy.Delete_management("finalslave%s" % (mycount-1))

############################################################################
## MAke final elevation difference
mytitle = "Final elevation difference"
#arcpy.Resample_management(sdemname,r"in_memory/sDEM%s" % mycount,arcpy.GetRasterProperties_management("mDEM","CELLSIZEX"),"BILINEAR")
#dH_matrix,dH,xdata,ydata,sdata = preprocess(tempshape,slope_raster,aspect_raster,arcpy.Raster("mDEM"),slaveDEM_adj)

## Export the elevation sample used for co-registration
ll = arcpy.Point(dH.extent.XMin,dH.extent.YMin)
newRaster = arcpy.NumPyArrayToRaster(dH_matrix,ll,dH.meanCellWidth,dH.meanCellHeight)
newRaster.save(dHpost_sample)
## Export full dh and sample used
dHFinal.save(dHpost)
#arcpy.CopyRaster_management(dHFinal,dHpost,"","","","","",arcpy.Raster(snameorig).pixelType,"","")
slaveDEM_adj.save( os.path.basename(snameorig[:-4]) + "_adj.tif")
pp.close()
############################################################################
arcpy.Delete_management("finalslave%s" % (mycount))
arcpy.Delete_management(tempshape)
arcpy.Delete_management("in_memory")
arcpy.Delete_management("mDEM")
del slope_raster
del aspect_raster
del masterDEM_raster
del slaveDEM_raster
del outmask1
del outmask2
arcpy.Delete_management("outmask1")
arcpy.Delete_management("outmask2")

############################################################################
print ("Finished")
