from r_numpy_lib import *
from multiprocessing import Pool,Process
import multiprocessing
###################################################################################################
#Parameters that rarely need changed

#Directories

#Location of GEE TDD Composites
gee_composite_dir = 'T:/baseline/TDD_baseline_data/rtfd-exports/'

# #Location of GTAC Composites
# local_composite_dir = 'J:/'

# #Location of final outputs
# final_output_dir = 'J:/'

#Location of GTAC Composites
local_composite_dir = 'T:/storage/'

#Location of final outputs
final_output_dir = 'T:/storage/'


#Location of final outputs on T drive
final_outputs_dir_T = 'T:/FS/NFS/WOEngineering/GMO-GTAC/Project/RATI/FHAAST/FDM/'

#Location of TDD outputs
processing_base = 'T:/storage/TDD_processing/'

#Location of masks for Hansen change and Ellenwood forest 
hansen_msk_dir = 'T:/storage/Hansen/mz_msks/'

#Location of gdal fwTools binaries
gdal_dir = 'C:/Python38/Lib/site-packages/osgeo/'
###################################################################################################
#Number of days (inclusive) each period includes
#Compositing every 16 days would have a julianSpan of 15
julianSpan = 15

#Number of years to include in the TDD trend analysis
nYears = 5

#Number of threads to run (generally the same as the number of multi-zones)
nThreads = 14

#Brown down minimum slope for min-max stretch
bd_in_min = -1100.0
#Brown down maximum slope for min-max stretch
bd_in_max = 0.0

#Brown down output min
bd_out_min = 0

#Brown down output max
bd_out_max = 250

#Template for tfw file
tfw_template = '240.00000000000000\n0.0\n0.0\n-240.00000000000000\n-2370825.0000000000\n3189195.0000000000'

#Zones to be merged for persistence calculations.  Each set of multi-zones should be in its own list
persistence_merge_list = [[1,2,3,5,6,7],[4],[8,9,10,11,12,13,14]]

#Bands for computing indices from GEE composites
ndvi_bands_gee = [2,1]
ndmi_bands_gee = [2,5]

#Bands for computing indices for GTAC composites
ndvi_bands_local = [2,1]
ndmi_bands_local = [2,7]

#Which zones for NDMI or NDVI
ndmiZones = [1,2,3,4,5,6,7]
ndviZones = [8,9,10,11,12,13,14]

#All zones to process
mzs = list(range(1,15))

#Different band possibilities for different masking scenarios
band_possibilities = [[1,2,3,4,5],\
        [1,2,3,5],\
        [1,2,4,5],\
        [1,3,4,5],\
        [2,3,4,5],\
        [1,2,5],\
        [1,3,5],\
        [1,4,5],\
        [2,3,5],\
        [2,4,5],\
        [3,4,5]]

#Names of outputs from linear fit
layer_names = ['slope', 'b', 'r2','RMSE']

#Get teh forest masks
forest_masks = glob(hansen_msk_dir,'.tif')
###################################################################################################
###################################################################################################
#Set up different color tables and names
tracking_mask_ct = gdal.ColorTable()
tracking_mask_ct.SetColorEntry(0, (0, 0, 150, 255))
tracking_mask_ct.SetColorEntry(1, (0, 170, 0, 255))
tracking_mask_ct.SetColorEntry(2, (170, 170, 0, 255))
tracking_mask_ct.SetColorEntry(3, (200, 0, 0, 255))

tracking_mask_names = ['Data all 5 years (processed)','Data >= 2/4 previous years and most recent year (processed)','Data most recent year but not >= 2/4 previous years (not processed)','No data most recent year (not processed)']



combined_ct = gdal.ColorTable()
combined_ct.SetColorEntry(0, (0, 170, 0, 255))
combined_ct.SetColorEntry(2, (0, 170, 170, 255))
combined_ct.SetColorEntry(3, (170, 170, 0, 255))
combined_ct.SetColorEntry(4, (170, 0, 0, 255))
combined_ct.SetColorEntry(5, (170, 170, 170, 255))

combined_names = ['Forest Ellenwood and Hansen','None','Data most recent year but not >= 2/4 previous years','No data most recent year','Non Forest Only Hansen','Non Forest Ellenwood and Hansen']



bd_ct =  gdal.ColorTable()
for i in range(0,150):bd_ct.SetColorEntry(i,(200,0,0,255))
bd_ct.CreateColorRamp(150, color_dict['red'], 240, color_dict['orange'])
bd_ct.CreateColorRamp(240, color_dict['orange'], 250, color_dict['green'])
bd_ct.SetColorEntry(252,(0,0,170,255))
bd_ct.SetColorEntry(253,(170,170,170,255))
bd_ct.SetColorEntry(254,(255,255,0,255))
bd_ct.SetColorEntry(255,(205,185,156,255))

bd_names = [str(i) + ' slope' for i in range(0,251)]
bd_names.extend(['None','Data most recent year but not >= 2/4 previous years','No data most recent year','Non Forest Only Hansen','Non Forest Ellenwood and Hansen'])



persistence_ct = gdal.ColorTable()
persistence_ct.SetColorEntry(0, (225, 225, 225, 255))
persistence_ct.SetColorEntry(1, (255, 170, 0, 255))
persistence_ct.SetColorEntry(2, (255, 0, 0, 255))
persistence_ct.SetColorEntry(3, (255, 0, 197, 255))
persistence_ct.SetColorEntry(252, (230, 230, 0, 255))
persistence_ct.SetColorEntry(253, (168, 112, 0, 255))
persistence_ct.SetColorEntry(254, (0, 197, 255, 255))
persistence_ct.SetColorEntry(255,(205,185,156,255))

persistence_names = ['No Change','Detectable Departure','Moderate Deparature','Severe Departure']
persistence_names.extend(['None' for i in range(4,251)])
persistence_names.extend(['None','No data in at least one of the prior 2 compositing periods','No data most recent compositing period','Non Forest Only Hansen','Non Forest Ellenwood and Hansen'])
########################################################################################################
########################################################################################################
#Function that classifies continuous tdd slope data into 15 classes
def classify_persistence(slp1,slp2,slp3,std1,std2,no_data,out_no_data):
    out = numpy.zeros_like(slp1,'u1')

    out[(slp1 == no_data) | (slp2 == no_data) | (slp3 == no_data)] = out_no_data
    
    print('Classifying class',2)
    #if (west_tdd209 le %std2091% & west_tdd217 le %std2171% & west_tdd225 gt %std2251%) w_tdd09225_2 = 2
    out[(out != out_no_data)  & (slp1 <= std1[0]) & (slp2 <= std1[1]) & (slp3 > std1[2])] = 2

    print('Classifying class',3)
    #if (west_tdd209 le %std2091% & west_tdd217 gt %std2171% & west_tdd225 le %std2251%) w_tdd09225_3 = 3
    out[(out != out_no_data)  & (slp1 <= std1[0]) & (slp2 > std1[1]) & (slp3 <= std1[2])] = 3

    print('Classifying class',4)
    #if (west_tdd209 gt %std2091% & west_tdd217 le %std2171% & west_tdd225 le %std2251%) w_tdd09225_4 = 4
    out[(out != out_no_data)  & (slp1 > std1[0]) & (slp2 <= std1[1]) & (slp3 <= std1[2])] = 4

    print('Classifying class',5)
    #if (west_tdd209 le %std2091% & west_tdd217 le %std2171% & west_tdd225 le %std2251%) w_tdd09225_5 = 5
    out[(out != out_no_data)  & (slp1 <= std1[0]) & (slp2 <= std1[1]) & (slp3 <= std1[2])] = 5

    print('Classifying class',6)
    #if (west_tdd209 le %std2091% & west_tdd217 le %std2171% & west_tdd225 le %std2252%) w_tdd09225_6 = 6
    out[(out != out_no_data)  & (slp1 <= std1[0]) & (slp2 <= std1[1]) & (slp3 <= std2[2])] = 6

    print('Classifying class',7)
    #if (west_tdd209 le %std2091% & west_tdd217 le %std2172% & west_tdd225 le %std2251%) w_tdd09225_7 = 7
    out[(out != out_no_data)  & (slp1 <= std1[0]) & (slp2 <= std2[1]) & (slp3 <= std1[2])] = 7

    print('Classifying class',8)
    #if (west_tdd209 le %std2092% & west_tdd217 le %std2171% & west_tdd225 le %std2251%) w_tdd09225_8 = 8
    out[(out != out_no_data)  & (slp1 <= std2[0]) & (slp2 <= std1[1]) & (slp3 <= std1[2])] = 8

    print('Classifying class',9)
    #if (west_tdd209 le %std2092% & west_tdd217 le %std2172% & west_tdd225 gt %std2251%) w_tdd09225_9 = 9
    out[(out != out_no_data)  & (slp1 <= std2[0]) & (slp2 <= std2[1]) & (slp3 > std1[2])] = 9

    print('Classifying class',10)
    #if (west_tdd209 le %std2092% & west_tdd217 gt %std2171% & west_tdd225 le %std2252%) w_tdd09225_10 = 10
    out[(out != out_no_data)  & (slp1 <= std2[0]) & (slp2 > std1[1]) & (slp3 <= std2[2])] = 10

    print('Classifying class',11)
    #if (west_tdd209 gt %std2091% & west_tdd217 le %std2172% & west_tdd225 le %std2252%) w_tdd09225_11 = 11
    out[(out != out_no_data)  & (slp1 > std1[0]) & (slp2 <= std2[1]) & (slp3 <= std2[2])] = 11

    print('Classifying class',12)
    #if (west_tdd209 le %std2092% & west_tdd217 le %std2172% & west_tdd225 le %std2251%) w_tdd09225_12 = 12
    out[(out != out_no_data)  & (slp1 <= std2[0]) & (slp2 <= std2[1]) & (slp3 <= std1[2])] = 12

    print('Classifying class',13)
    #if (west_tdd209 le %std2092% & west_tdd217 le %std2171% & west_tdd225 le %std2252%) w_tdd09225_13 = 13
    out[(out != out_no_data)  & (slp1 <= std2[0]) & (slp2 <= std1[1]) & (slp3 <= std2[2])] = 13

    print('Classifying class',14)
    #if (west_tdd209 le %std2091% & west_tdd217 le %std2172% & west_tdd225 le %std2252%) w_tdd09225_14 = 14
    out[(out != out_no_data)  & (slp1 <= std1[0]) & (slp2 <= std2[1]) & (slp3 <= std2[2])] = 14

    print('Classifying class',15)
    #if (west_tdd209 le %std2092% & west_tdd217 le %std2172% & west_tdd225 le %std2252%) w_tdd09225_15 = 15
    out[(out != out_no_data)  & (slp1 <= std2[0]) & (slp2 <= std2[1])& (slp3 <= std2[2])] = 15

    print('Classifying class',1)
    #if (west_tdd209 gt %std2091% & west_tdd217 gt %std2171% & west_tdd225 gt %std2251%) w_tdd09225_1 = 1
    out[(out != out_no_data)  & (slp1 > std1[0]) & (slp2 > std1[1])& (slp3 > std1[2])] = 1


    out[out == 0] = out_no_data

    slp1,slp2,slp3 = None,None,None
    return out
########################################################################################################
#Function to reclass the 15 class output from the classify persistence function
#Original code:
    ##1  1  :  0
    ##2  6  :  1
    ##7  11  :  2
    ##12  15  :  3
def persistence_3class(in_array,out_no_data):
    print('Binning persistence into 3 classes')
    out_3cl = numpy.zeros_like(in_array,'u1')

    out_3cl[(in_array >= 2) & (in_array <= 6)] = 1
    out_3cl[(in_array >= 7) & (in_array <= 11)] = 2
    out_3cl[(in_array >= 12) & (in_array <= 15)] = 3
    out_3cl[in_array == out_no_data] = out_no_data
    in_array = None
    return out_3cl
########################################################################################################
#Function to reclass the 15 class output from the classify persistence function
#Original code:
    ##1  :  0
    ##2  :  1
    ##3  :  0
    ##4  :  0
    ##5  :  1
    ##6  :  1
    ##7  :  2
    ##8  :  2
    ##9  :  0
    ##10  :  0
    ##11  :  2
    ##12  :  3
    ##13  :  3
    ##14  :  3
    ##15  :  3
def persistence_3class_last2(in_array,out_no_data):
    print('Binning persistence into 3 classes last 2')
    out_last2 = numpy.zeros_like(in_array,'u1')
    out_last2[(in_array == 2) |(in_array == 5) | (in_array == 6)] = 1
    out_last2[(in_array == 7) |(in_array == 8) | (in_array == 11)] = 2
    out_last2[(in_array == 12) |(in_array == 13) | (in_array == 14)| (in_array == 15)] = 3
    out_last2[in_array == out_no_data] = out_no_data
    in_array = None
    return out_last2
########################################################################################################
#Function to get a normalized difference from a given 3-d array
#Assumes the first dimension has length 2
def get_nd(b):
    print(b.shape)
    b = numpy.array(b,dtype = 'Float32')
    print('Computing normalized difference')
    denom = (b[0] + b[1])
    denom[denom == 0] = 1
    nd = ((b[0] - b[1]) / denom)
    denom = None
    nd[(b[0] + b[1]) == 0] = 0
    b = None
    return nd
########################################################################################################
#Wrapper for applying the inear fit for a multizone across a set of band combos
def batch_lm(out_nd,bp_set,years,output_temp_folder,out_fit_template):
    #Iterate across each band set 
    for band_possibility in bp_set:
        yearsT =  [years[i-1] for i in band_possibility]
        bp_str = '_'.join([str(i) for i in band_possibility])
        out_fitT = output_temp_folder +out_fit_template  +'_'+bp_str + '.tif'
       
        if os.path.exists(out_fitT) == False:
            new_big_image_matrix_linregress(out_nd,out_fitT, years = yearsT, in_no_data = -32768,out_no_data = -32768, mem_size_limit = 10000000, layer_names = [], band_list =band_possibility,dt = 'Float32')
########################################################################################################
#Function to reduce all of the different band combo slopes into a single raster
def combine_fits(layer_no,layer_name,output_folder,out_fit_template,out_fits):
            
    fit_array_exists = False
    out_fitT = output_folder +out_fit_template + '_'+layer_name+'.tif'
    if os.path.exists(out_fitT) == False:
        print(('Combining rasters to create:',out_fitT))

        #Iterate across each fit and include its value if its not nodata and the pixel has not been included yet
        for fit in out_fits:

            #Read in raster
            r = raster(fit, dt = 'Float32', band_no = layer_no, xoffset = 0, yoffset = 0, width = '', height = '')
        
            if not fit_array_exists:
                fit_array = r
                fit_array_exists = True
            else:
                fit_array = numpy.where((fit_array == -32768) & (r != -32768), r,fit_array)
            r = None
        
        #Write output and update stats
        write_raster(fit_array,out_fitT, template = out_fits[0],dt = 'Float32', compress = True)
        raster_info(out_fitT,True)
        fit_array = None
    else:
        print(('Already combined:',base(out_fitT)))
########################################################################################################
#Wrapper for computing the normalized index and linear fit
def mzIndexAndFit(mz,year,startJulian,endJulian,nYears):

    #Set up folders and different elements for the given mz and compositing period
    forest_mask = [i for i in forest_masks if base(i).find('MZ'+ format(mz,'02')) > -1][0]
   
    startJulianStr = format(startJulian, '03')
    endJulianStr = format(endJulian,'03')
    jd_str_pair = startJulianStr + '_'+endJulianStr

    #Find the template mask for the mz to use for masking and snapping
    template_mask = glob_end(hansen_msk_dir,'MZ' + format(mz,'02')+'_rtfdmskup.tif')[0]
    m_info = raster_info(template_mask)

    folder_base = check_end(processing_base) + str(year) +'/'+ startJulianStr + '/'
    input_folder = folder_base + 'linear_fit_inputs_'+startJulianStr+'/'
    output_folder= folder_base + 'linear_fit_outputs_'+startJulianStr+'/'
    output_folder_240 =  folder_base + 'linear_fit_outputs_'+startJulianStr+'_240m/'
    
    output_temp_folder = output_folder + 'temp/'
    check_dir(input_folder)
    check_dir(output_temp_folder)
    check_dir(output_folder_240)
    years = list(range(year-nYears+1,year+1))
    year_range_str = str(years[0]) + '_' + str(years[-1])

    #Find whether it's NDMI or NDVI
    if mz in ndmiZones:
        indexName = 'NDMI'
    else:
        indexName = 'NDVI'

    #Iterate across each year in the trend period to see if there's a refl available
    refl_stack_list = []
    for yr in years:
        refls = []
        #Set up the GTAC local compositing directory for the period
        local_composite_dir_jd = check_end(local_composite_dir) + str(yr) + '_Composites/' +jd_str_pair+'/'

        #If that directory exists, find what refls are available for the mz and compositing period
        if os.path.exists(local_composite_dir_jd) and yr == years[-1]:
            refls  = glob_end(local_composite_dir_jd,'zone'+format(mz,'02')+ '_'+jd_str_pair+'_nrt_composite_surface_reflectance_240.img')
           
        #Otherwise, look for GEE-based refls
        elif not os.path.exists(local_composite_dir_jd) or len(refls) == 0 :
            refls = glob_end(gee_composite_dir,'MZ'+format(mz,'02') + '_'+ str(yr)+'_'+str(yr)+ '_'+jd_str_pair+ '.tif')
        
        #Expects there to only be one available for each compositing period/mz combo
        #If so, append it to the list
        if len(refls) == 1:
            refl_stack_list.append(refls[0])

    #If the number of refls is the same as the years, process it
    if(len(refl_stack_list) == len(years)):
       
        #Set up the outputs for the normalized difference, slope, and tracking mask
        out_nd = input_folder + 'MZ'+format(mz,'02') + '_'+year_range_str + '_'+ jd_str_pair  + '_'+indexName+'.tif'
        out_fit_template = 'MZ'+format(mz,'02') + '_'+year_range_str + '_'+ jd_str_pair  + '_'+indexName+'_fit'
        tracking_mask = os.path.splitext(out_nd)[0] + '_tracking_mask.tif'
        slope_raster = output_folder +out_fit_template + '_slope.tif'

        ########################################################
        #Compute the normalized difference
        if os.path.exists(out_nd) == False:
            
          
            #Get some info about the last image (expected to be the best for a template)
            ras_info = raster_info(refl_stack_list[-1])
            coords = ras_info['coords']
            res = ras_info['res']

            #Find out the size of it and set up the output raster extent based on it
            out_ncolumn = int(numpy.floor((coords[2]-coords[0])/res))
            out_nrow =  int(numpy.floor((coords[3] - coords[1])/res))
            array_stack =  numpy.zeros([len(refl_stack_list), out_nrow, out_ncolumn], dtype = 'Int16')
            tracking_mask_array =  numpy.zeros([out_nrow, out_ncolumn], dtype = 'u1')
            
            #Iterate across each refl and compute the normalized difference
            i = 0
            for refl in refl_stack_list:
                #Find the bands for whether the composite is a local or GEE composite
                if refl.find(local_composite_dir_jd) > -1:
                    
                    if mz in ndmiZones:
                        ndBands = ndmi_bands_local
                    else:
                        ndBands = ndvi_bands_local
                else:
                    if mz in ndmiZones:
                        ndBands = ndmi_bands_gee
                    else:
                        ndBands = ndvi_bands_gee
                
                #Set the no data
                ri = raster_info(refl)
                no_data = ri['no_data']
                if no_data == None:
                    no_data = 0
                
                transform = ri['transform']

                #Find the piece of the raster that overlaps with the output (Generally GEE is a bit different than locally computed composites)
                column_offset =  int(numpy.floor(((coords[0] - transform[0])/res)))#+1
                row_offset = int( numpy.floor(((transform[3]- coords[3] )/res)))#+1

                #Read in the raster to memory
                b = brick(refl, dt = 'Float32', xoffset = column_offset, yoffset = row_offset, width = out_ncolumn, height = out_nrow, band_list = ndBands)
                
                #Compute the normalized difference
                nd =get_nd(b)
                #Scale it by 10000
                nd = nd * 10000
                #Burn in the nodata
                nd[b[0] == no_data] =-32768
                b = None

                #Insert it into the output normalized difference stack
                array_stack[i] = nd
                nd = None

                i +=1
            
            #Find different combos of no data
            #Start with the prior years
            previous_four_masked_count = numpy.sum(array_stack[0:-1] == -32768,0)

            #If only 1 or 2 of the prior years is masked, code to 1
            tracking_mask_array[previous_four_masked_count >= 1] = 1

            #If more than 2 of the prior years are masked, code to 2
            tracking_mask_array[previous_four_masked_count > 2] = 2
            previous_four_masked_count = None
            
            #If the most recent year is masked, code to 3
            tracking_mask_array[array_stack[-1] == -32768] = 3

            #Burn in no data to any pixel that has the most recent or more than 2 of the prioe years masked 
            array_stack[:,tracking_mask_array > 1] = -32768
            
            #Write out the normalized difference stack and tracking mask
            write_raster(tracking_mask_array,tracking_mask, template = refl_stack_list[-1], dt = 'Byte',compress = True,ct = tracking_mask_ct,names = tracking_mask_names)
            tracking_mask_array = None
            stack(array_stack, out_nd,  refl_stack_list[-1],  dt = 'Int16', array_list = True,compress = False)
            array_stack = None

            set_no_data(out_nd,-32768,True)
        else:
            print(('Already computed',base(out_nd)))
       

        ########################################################
        #Apply the linear fit for different band possibilities
        #Currently runs 5 proceeses concurrently
        out_fits = []
        bp_sets = new_set_maker(band_possibilities,3)
        
        for bp_set in bp_sets:
            p = Process(target = batch_lm,args = (out_nd,bp_set,years,output_temp_folder,out_fit_template,))
            p.start()
            time.sleep(0.2)
        while len(multiprocessing.process.active_children()) > 0:
            time.sleep(5)

        #Find the output slopes and sort them in descending order from most obs to least
        out_fitsT = glob_find(output_temp_folder,'MZ' + format(mz,'02'))
        out_fitsT = [i for i in out_fitsT if os.path.splitext(i)[1] == '.tif']
        
        out_fits = []

        for bp in band_possibilities:
            bp_str = '_'+'_'.join([str(i) for i in bp])
            out_fitsTT = [i for i in out_fitsT if os.path.basename(i).find('_fit'+ bp_str + '.tif') > -1]
            out_fits.append(out_fitsTT[0])
        
        
        #Combine the different slopes to a single slope prioritizing the value with the most observations
        for layer_no in range(1,len(layer_names)+1):
            layer_name = layer_names[layer_no-1]
            
            p = Process(target = combine_fits,args = (layer_no,layer_name,output_folder,out_fit_template,out_fits,))
            p.start()
            time.sleep(0.2)
        while len(multiprocessing.process.active_children()) > 0:
            time.sleep(5)
          
        ########################################################
        #Convert to 240 (if not already done) and snap to final grid
        slope_raster_240 = output_folder_240 + base(slope_raster) + '_240m.tif'
        tracking_mask_240 = output_folder_240 + base(tracking_mask) + '_240m.tif'
        combined_tracking_mask_240 = output_folder_240 + base(tracking_mask) + '_combined_240m.tif'
        slope_raster_masked_240 =  output_folder_240 + base(slope_raster) + '_240m_masked.tif'
        slope_raster_masked_bd_240 =  output_folder_240 + base(slope_raster) + '_240m_masked_bd.tif'

        
        if os.path.exists(slope_raster_240) == False:
            reproject(slope_raster,slope_raster_240,m_info['proj4'],res = m_info['res'],clip_extent = m_info['coords'],resampling_method = 'cubic', src_no_data = -32768,dst_no_data = -32768,gdal_dir =gdal_dir)
        if os.path.exists(tracking_mask_240) == False:
            reproject(tracking_mask,tracking_mask_240,m_info['proj4'],res = m_info['res'],clip_extent = m_info['coords'],resampling_method = 'near',dst_no_data = 255,gdal_dir =gdal_dir)
            update_color_table_or_names(tracking_mask_240,color_table = tracking_mask_ct,names = tracking_mask_names)
       
        #Combine tracking mask with predefined Hansen and Ellenwood mask values
        if os.path.exists(combined_tracking_mask_240) == False:
            #Read in each mask
            fm = raster(forest_mask)
            tracker = raster(tracking_mask_240)
            
            out = numpy.zeros_like(fm)
            
            #Bring in the masked values for the composite
            out[tracker == 3] = 3
            out[tracker == 2] = 2
            tracker = None
            #Bring in the Hansen and Ellenwood codes (1 and 0 respectively)
            out[fm == 1] = 0 #Changed from 4 to 0 so Hansen mask is not applied (June 2, 2020)
            out[fm == 0] = 5
            out[fm == 255] = 255
            fm = None
            write_raster(out,combined_tracking_mask_240,tracking_mask_240,assume_ct_names = False,out_no_data = 255,dt = 'u1',ct = combined_ct,names = combined_names)
            out = None
            
            
        #Burn in mask values to slope output
        if os.path.exists(slope_raster_masked_240) == False:
            m = raster(combined_tracking_mask_240)
            slp = raster(slope_raster_240,dt = 'Float32')

            slp[m > 1] = -32768
            write_raster(slp,slope_raster_masked_240,slope_raster_240,dt = 'Float32')

            slp = None
            m = None

        #Convert slope to browndown
        if os.path.exists(slope_raster_masked_bd_240) == False:
            #Bring in mask
            m = raster(combined_tracking_mask_240)

            #Bring in slope
            slp = raster(slope_raster_masked_240,dt = 'Float32')

            #Convert slope to browndown with min-max stretch
            bd = ((slp - bd_in_min) * bd_out_max) / (bd_in_max- bd_in_min)

            
            #Clamp output to fall within range 
            bd[bd > bd_out_max] = bd_out_max
            bd[bd < bd_out_min] = bd_out_min
            # bd[slp == -32768] = 255

            #Burn in mask values
            bd = numpy.where((m>=2) & (m <= 10), m+250,bd)
            bd = numpy.where(m==255, 255,bd)
            slp = None
            m = None
            write_raster(bd,slope_raster_masked_bd_240,slope_raster_masked_240,dt = 'u1',ct = bd_ct,names = bd_names,out_no_data = 255)
            bd = None
########################################################################################################
########################################################################################################
#Code for merging multi-zones

#Wrapper for merging slopes       
def merge_bd_slopes(bd_slopes,merged_bd_slopes):
    if os.path.exists(merged_bd_slopes) == False:
        simple_merge(bd_slopes,merged_bd_slopes,no_data = 255)
    update_color_table_or_names(merged_bd_slopes,color_table = bd_ct, names = bd_names)
    set_no_data(merged_bd_slopes, no_data_value = -1, update_stats = True)

#Wrapper for merging tracking masks
def merge_tracking_masks(tracking_masks,merged_tracking_masks):
    if os.path.exists(merged_tracking_masks) == False:
        simple_merge(tracking_masks,merged_tracking_masks,no_data = 255)
    update_color_table_or_names(merged_tracking_masks,color_table =  combined_ct,names = combined_names)

#Wrapper for merging different groups of multi-zones for persistence
def merge_persistence(l,raw_slopes,tracking_masks,merged_raw_base,merged_mask_base):

    raw_slopes_t = []
    tracking_masks_t = []
    for n in l:
        raw_slopes_t.extend([i for i in raw_slopes if base(i).find('MZ'+ format(n,'02')) > -1])
        tracking_masks_t.extend([i for i in tracking_masks if base(i).find('MZ'+ format(n,'02')) > -1])
    out_merge_slope = os.path.splitext(merged_raw_base)[0] + '_'+format(l[0],'02')+'_'+ format(l[-1],'02') + '.tif'
    out_merge_mask = os.path.splitext(merged_mask_base)[0] + '_'+format(l[0],'02')+'_'+ format(l[-1],'02') + '.tif'

    if os.path.exists(out_merge_slope) == False:
        simple_merge(raw_slopes_t,out_merge_slope,no_data = -32768)
    set_no_data(out_merge_slope, no_data_value = -32768, update_stats = True)
    # if os.path.exists(out_merge_mask) == False:
    #     simple_merge(tracking_masks_t,out_merge_mask,no_data = 255)
    #     update_color_table_or_names(out_merge_mask,color_table =  combined_ct,names = combined_names)

########################################################################################################
#Big wrapper for merging
def merge_mzs(year,startJulian,endJulian,nYears,persistence_merge_list,tracking_mask_end = '_tracking_mask_combined_240m.tif',raw_slope_end = '_fit_slope_240m_masked.tif',bd_slope_end = '_fit_slope_240m_masked_bd.tif'):
    #Set up directories and stuff
    startJulianStr = format(startJulian, '03')
    endJulianStr = format(endJulian,'03')
    jd_str_pair = startJulianStr + '_'+endJulianStr
    years = list(range(year-nYears+1,year+1))
    year_range_str = str(years[0]) + '_' + str(years[-1])
    folder_base = check_end(processing_base) + str(year) +'/'+ startJulianStr + '/'
    input_folder = folder_base + 'linear_fit_inputs_'+startJulianStr+'/'
    output_folder= folder_base + 'linear_fit_outputs_'+startJulianStr+'/'
    output_folder_240 =  folder_base + 'linear_fit_outputs_'+startJulianStr+'_240m/'
    pp_folder =  folder_base + 'linear_fit_outputs_'+startJulianStr+'_post_processing/'
    check_dir(pp_folder)


    #Find the browndown slopes, raw slopes, and tracking masks
    bd_slopes = glob_end(output_folder_240,bd_slope_end)
    raw_slopes = glob_end(output_folder_240,raw_slope_end)
    tracking_masks = glob_end(output_folder_240,tracking_mask_end)

    #Set up some outputs
    merged_bd_slopes = pp_folder +year_range_str +'_'+ jd_str_pair + '_merged'+ bd_slope_end
    merged_tracking_masks =  pp_folder +year_range_str +'_'+ jd_str_pair + '_merged'+ tracking_mask_end
    merged_raw_base =  pp_folder +year_range_str +'_'+ jd_str_pair + '_merged_for_persistence'+ raw_slope_end
    merged_mask_base =  pp_folder +year_range_str +'_'+ jd_str_pair + '_merged_for_persistence'+ tracking_mask_end

   
    #Kick off merge processes
    p = Process(target = merge_bd_slopes,args = (bd_slopes,merged_bd_slopes,))
    p.start()
    time.sleep(0.2)
    p = Process(target = merge_tracking_masks,args = (tracking_masks,merged_tracking_masks,))
    p.start()
    time.sleep(0.2)

    for l in persistence_merge_list:
        p = Process(target = merge_persistence, args = (l,raw_slopes,tracking_masks,merged_raw_base,merged_mask_base,))
        p.start()
        time.sleep(0.2)

    while len(multiprocessing.process.active_children()) > 0:
        print(len(multiprocessing.process.active_children()),':active merge subprocesses')
        time.sleep(5)

########################################################################################################
#Wrapper for persistence for a given set of multizones
def slope_merge_set_persistence(slope_merge_set):

    #Set up the persistence output names
    persistence_out = os.path.splitext(slope_merge_set[-1])[0] + '_persistence.tif'
    persistence_out_3c = os.path.splitext(slope_merge_set[-1])[0] + '_persistence_3class.tif'
    persistence_out_3c_l2 = os.path.splitext(slope_merge_set[-1])[0] + '_persistence_3class_last2.tif'
    
    
    #Set up the raw persistence and get the stats
    if os.path.exists(persistence_out) == False:
        p_ti = tiled_image(persistence_out,slope_merge_set[-1],dt = 'Byte',outline_tiles = True, size_limit_kb = 2000000,out_no_data = None,compression = True)
        
        # print(persistence_out)
        std1_list = []
        std2_list = []
        for s in slope_merge_set:
            stats = raster_info(s, band_no = 1, get_stats = True)
            m = stats['mean']
            std = stats['std']
            std1 = m- std*1.25
            std2 = m-std*2.25
            std1_list.append(std1)
            std2_list.append(std2)

        #Compute persistence for each chunk
        i2 = 1
        for xo,yo,w,h in p_ti.chunk_list:
            print('Processing chunk',i2,'/',len(p_ti.chunk_list))
            slp1 = raster(slope_merge_set[0],'i2',1,xo,yo,w,h)
            slp2 = raster(slope_merge_set[1],'i2',1,xo,yo,w,h)
            slp3 = raster(slope_merge_set[2],'i2',1,xo,yo,w,h)

            persist = classify_persistence(slp1,slp2,slp3,std1_list,std2_list,-32768,255)
            p_ti.add_tile(persist,xo,yo)
            i2+=1
            persist = None
            slp1 = None
            slp2 = None
            slp3 = None
        p_ti.rm()
        raster_info(persistence_out,1,True)

    #Bin up persistence
    if os.path.exists(persistence_out_3c) == False:
        print('doesnt exist')
        persistR = raster(persistence_out,dt = 'u1')
        p3c = persistence_3class(persistR,255)
        write_raster(p3c,persistence_out_3c,persistence_out,dt = 'u1',compress = True)
        p3c = None
        update_color_table_or_names(persistence_out_3c,color_table = persistence_ct,names = persistence_names)

        p3cl2 = persistence_3class_last2(persistR,255)
        write_raster(p3cl2,persistence_out_3c_l2,persistence_out,dt = 'u1',compress = True)
        p3cl2 = None
        persistR = None
        
        update_color_table_or_names(persistence_out_3c_l2,color_table = persistence_ct,names = persistence_names)
        set_no_data(persistence_out_3c_l2, no_data_value = -1, update_stats = False)

########################################################################################################
#Big wrapper for persistence
def compute_persistence(year,startJulian,endJulian,nYears,persistence_merge_list, period_length = 15,period_frequency = 8):
    
    #Set up the julian periods to look for
    t1_startJulian = startJulian - period_frequency * 2
    t1_endJulian = endJulian - period_frequency * 2

    t2_startJulian = startJulian - period_frequency * 1
    t2_endJulian = endJulian - period_frequency * 1
    
    t3_startJulian = startJulian
    t3_endJulian = endJulian

    julian_sets = [[t1_startJulian,t1_endJulian],[t2_startJulian,t2_endJulian],[t3_startJulian,t3_endJulian]]
    
    #Find whether all periods exist
    can_compute_persistence = True
    slope_merges = []
    tracking_masks = []
    for js in julian_sets:
        startJulianStr = format(js[0], '03')
        endJulianStr = format(js[1],'03')
        jd_str_pair =  startJulianStr+ '_'+endJulianStr
        folder_base = check_end(processing_base) + str(year) +'/'+ startJulianStr + '/'
    
        pp_folder =  folder_base + 'linear_fit_outputs_'+startJulianStr+'_post_processing/'
        if not os.path.exists(pp_folder):
            print ('No post processing folder')
            can_compute_persistence = False
            break
        else:
            merges = glob_find(pp_folder,'_merged_for_persistence_fit_slope')
            tracking_mask = glob_end(pp_folder,'_merged_tracking_mask_combined_240m.tif')[0]
            tracking_masks.append(tracking_mask)
            
            merges = [i for i in merges if base(i).find('.tif.aux') == -1 and os.path.basename(i).find('_persistence.tif') == -1  and os.path.basename(i).find('3class') == -1]
           
            if len(merges) == len(persistence_merge_list):
                slope_merges.append(merges)
            else:
                print ('Insufficient merges')
                print((len(merges) , len(persistence_merge_list)))
                can_compute_persistence = False
                break
            
    
    #If all 3 periods exist, comput persistence
    if can_compute_persistence:
        slope_merges = transpose(slope_merges)
        print(('Can compute persistence for',startJulian))

        persistence_out_list = []
        persistence_out_3c_list = []
        persistence_out_3c_l2_list = []

        persistence_out_merged = slope_merges[0][-1].split('_merged_for_persistence_fit_slope')[0] + '_persistence_merged.tif'
        persistence_out_merged_3c = slope_merges[0][-1].split('_merged_for_persistence_fit_slope')[0] + '_persistence_3class_merged.tif'
        persistence_out_merged_3c_l2 = slope_merges[0][-1].split('_merged_for_persistence_fit_slope')[0] + '_persistence_3class_last2_merged.tif'

        persistence_out_merged_updated = os.path.splitext(persistence_out_merged)[0] + '.updated'
        persistence_out_merged_3c_updated = os.path.splitext(persistence_out_merged_3c)[0] + '.updated'
        persistence_out_merged_3c_l2_updated = os.path.splitext(persistence_out_merged_3c_l2)[0] + '.updated'
        

        #Compute persistence for each mz set
        for slope_merge_set in slope_merges:
            p = Process(target = slope_merge_set_persistence,args = (slope_merge_set,))
            p.start()
            time.sleep(0.2)
        while len(multiprocessing.process.active_children()) > 0:
            print(len(multiprocessing.process.active_children()),':active persistence processes')
            time.sleep(5)

        #Merge persistence outputs for CONUS output
        persistence_raws = glob_end(pp_folder,'_persistence.tif')
        persistence_3cs = glob_end(pp_folder,'_persistence_3class.tif')
        persistences_3c_l2s = glob_end(pp_folder,'_persistence_3class_last2.tif')

        if os.path.exists(persistence_out_merged) == False:
            print('merging')
            p1 = Process(target = simple_merge,args = (persistence_raws,persistence_out_merged,255,))
            p1.start()
            time.sleep(0.2)
        if os.path.exists(persistence_out_merged_3c) == False:
            p2 = Process(target = simple_merge,args = (persistence_3cs,persistence_out_merged_3c,255,))
            p2.start()
            time.sleep(0.2)
        if os.path.exists(persistence_out_merged_3c_l2) == False:
            p3 = Process(target = simple_merge,args = (persistences_3c_l2s,persistence_out_merged_3c_l2,255,))
            p3.start()
            time.sleep(0.2)
        while len(multiprocessing.process.active_children()) > 0:
            print(len(multiprocessing.process.active_children()),':active persistence merge processes')
            time.sleep(5)

       
        update_color_table_or_names(persistence_out_merged_3c,color_table = persistence_ct,names = persistence_names)
        update_color_table_or_names(persistence_out_merged_3c_l2,color_table = persistence_ct,names = persistence_names)
        set_no_data(persistence_out_merged_3c, no_data_value = -1, update_stats = False)
        set_no_data(persistence_out_merged_3c_l2, no_data_value = -1, update_stats = False)
        
        #Compute mask based on all 3 compositing periods and burn the resulting mask into final output
        if os.path.exists(persistence_out_merged_updated) == False\
         or os.path.exists(persistence_out_merged_3c_updated) == False\
         or os.path.exists(persistence_out_merged_3c_l2_updated) == False:

            #Open each tracking mask and find the areas with missing data
            tr_rast = raster(tracking_masks[0])
            out_tracker = numpy.zeros_like(tr_rast,'u1')
            out_tracker[out_tracker == 0] = 255

            out_tracker[tr_rast == 2] = 252
            out_tracker[tr_rast == 3] = 252
            out_tracker[tr_rast == 4] = 254
            tr_rast = None
            
            tr_rast = raster(tracking_masks[1])
            out_tracker[tr_rast == 2] = 252
            out_tracker[tr_rast == 3] = 252
            out_tracker[tr_rast == 4] = 254
            tr_rast = None

            tr_rast = raster(tracking_masks[2])
            out_tracker[tr_rast == 2] = 253
            out_tracker[tr_rast == 3] = 253
            out_tracker[tr_rast == 4] = 254

            tr_rast = None
            
            #Burn in the combined mask
            update_raster(persistence_out_merged,out_tracker,0,0,255)
            oo = open(persistence_out_merged_updated,'w')
            oo.close()

            update_raster(persistence_out_merged_3c,out_tracker,0,0,255)
            oo = open(persistence_out_merged_3c_updated,'w')
            oo.close()

            update_raster(persistence_out_merged_3c_l2,out_tracker,0,0,255)
            oo = open(persistence_out_merged_3c_l2_updated,'w')
            oo.close()
            
            tr_rast = None
            out_tracker = None
########################################################################################################
#Function for transferring files        
def transfer_files(year,startJulian,endJulian, bd_end = 'merged_fit_slope_240m_masked_bd.tif',persistence_end = '_persistence_3class_last2_merged.tif'):
    outputs_exist = False
    startJulianStr = format(startJulian, '03')
    endJulianStr = format(endJulian,'03')
    jd_str_pair = startJulianStr + '_'+endJulianStr
    years = list(range(year-nYears+1,year+1))
    year_range_str = str(years[0]) + '_' + str(years[-1])

    calendar = julian_to_calendar(endJulian, year)
    calendarStr = format(calendar['month'],'02') + format(calendar['day'],'02')
    folder_base = check_end(processing_base) + str(year) +'/'+ startJulianStr + '/'
    
    pp_folder =  folder_base + 'linear_fit_outputs_'+startJulianStr+'_post_processing/'
    final_output_folder = final_output_dir + str(year) + '_RTFD_Final_Outputs/'+ jd_str_pair + '/'
    if os.path.exists(final_output_folder) and os.path.exists(pp_folder):
        bd_output = glob_end(pp_folder,bd_end)
        persistence_output = glob_end(pp_folder,persistence_end)

        if len(bd_output) == 1:
            outputs_exist = True
            bd_output = bd_output[0]
            bd_final_name = final_output_folder + str(year) + calendarStr + '_16_5yr_bd.tif'
            if os.path.exists(bd_final_name) == False:
                print(('Copying:',bd_final_name))
                shutil.copy(bd_output,bd_final_name )

                oo = open(os.path.splitext(bd_final_name)[0]+ '.tfw','w')
                oo.writelines(tfw_template)
                oo.close()
      
        if len(persistence_output) == 1:
            persistence_output = persistence_output[0]
            persistence_final_name = final_output_folder + str(year) + calendarStr + '_32_5yr.tif'
            if os.path.exists(persistence_final_name) == False:
                print(('Copying:',persistence_final_name))
                shutil.copy(persistence_output,persistence_final_name )
            
                oo = open(os.path.splitext(persistence_final_name)[0]+ '.tfw','w')
                oo.writelines(tfw_template)
                oo.close()
    return outputs_exist
########################################################################################################
#Batch functions for multiprocessing
def batchMZIndexAndFit(mzs,year,startJulian,endJulian,nYears):
    for mz in mzs:
        mzIndexAndFit(mz,year,startJulian,endJulian,nYears)
def batchCompute(mzs,year,startJulian,endJulian,nYears):
    mzSets = new_set_maker(mzs,nThreads)
    for mzSet in mzSets:
        p = Process(target = batchMZIndexAndFit,args = (mzSet,year,startJulian,endJulian,nYears,))
        p.start()
        time.sleep(0.2)
    while len(multiprocessing.process.active_children()) > 0:
        print(len(multiprocessing.process.active_children()),':active index linear fit processes')

        time.sleep(5)
def isFinished(year,startJulian,endJulian):
    return transfer_files(year,startJulian,endJulian)
########################################################################################################
def runItAll(year,startJulians):
    for startJulian in startJulians:
        endJulian = startJulian + julianSpan
        outputs_exist = isFinished(year,startJulian,endJulian)
        if not outputs_exist:
            print('Computing TDD for:',year,startJulian,endJulian)
            batchCompute(mzs,year,startJulian,endJulian,nYears)
            merge_mzs(year,startJulian,endJulian,nYears,persistence_merge_list)
            compute_persistence(year,startJulian,endJulian,nYears,persistence_merge_list)
    #         transfer_files(year,startJulian,endJulian)
########################################################################################################
#End functions
