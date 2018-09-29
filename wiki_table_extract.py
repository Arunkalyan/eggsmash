
"""Create CSVs from all tables on a Wikipedia article."""
# Code fails for Table Within a Table at this time. Known Bug. Will Deal with it when there is a usecase. Very Rare

import csv
import os
import platform
import pandas as pd
import ast
import json
from bs4 import BeautifulSoup
import requests
import random
import uuid

def get_config(dirname, filename):
    """
    Read the config file and create the config obect
    """
    try:
        with open(dirname + filename) as jsonfile:
            config=json.load(jsonfile)
    except Exception as err:
        raise(err)
    return config

def scrape(url, output_folder, filetemplate,tabletype):
    """Create CSVs from all tables in a Wikipedia article.
    ARGS:
        url (str): The full URL of the Wikipedia article to scrape tables from.
        output_name (str): The base file name (without filepath) to write to.
    """

    # Read tables from Wikipedia article into list of HTML strings
    resp = requests.get(url)
    soup = BeautifulSoup(resp.content, 'lxml')
    # Added by Arun - Wikitable
    table_classes = {"class": [tabletype]}
    wikitables = soup.findAll("table", table_classes)

    # Create folder for output if it doesn't exist
    try:
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
    except Exception:  # Generic OS Error
        print ("Error in creating folder ",output_folder)
        pass

    for index, table in enumerate(wikitables):
        # Make a unique file name for each CSV

        filepath = os.path.join(output_folder,filetemplate + '_' + str(index)) + '.csv'

        try:
            write_html_table_to_csv(table,filepath)
        except Exception:
            print ("Error in table ",filepath)

def getLinkandValue(cell):
    # Get the link and value for each of the HREF datapoints
    matText = cell.text.replace('\xa0', ' ').replace('\n','')
    matLink = {}
    for a in cell.find_all('a', href=True):
        hrefText = a.text.replace('\xa0', ' ').replace('\n','')
        matLink[hrefText] = a['href']
        matText = matText.replace(hrefText, '')
    
    if len(matText.replace(',','').replace(' ','')) > 0:
        matLink[matText] = ""
    
    return matLink

def write_html_table_to_csv(table,filepath):
    """Write HTML table from Wikipedia to a CSV file.
    ARGS:
        table (bs4.Tag): The bs4 Tag object being analyzed.
        writer (csv.writer): The csv Writer object creating the output.
    """

    # Hold elements that span multiple rows in a list of
    # dictionaries that track 'rows_left' and 'value'

    
    saved_rowspans = []
    header_cols = []
    colspan=1
    colvalue=""
    rowL=0
    
    # Find Maximum Row and Columns
    for row in table.findAll("tr"):
        cells = row.findAll(["th", "td"])

        if len(header_cols) == 0:

             # Added by Arun - The code is not accounting for ColSpan
            for cell in cells:
                tempCell = repr(cell)
                header_soup = BeautifulSoup(tempCell,"lxml")
                try:
                    colspan = header_soup.find("th")['colspan']
                    colvalue = header_soup.select("th")[0].text
                except:
                    pass
                
                for x in range(int(colspan)):
                    saved_rowspans.append(None)
                    header_cols.append(colvalue)
                    
                colspan=1
                colvalue="" 
        rowL+=1
        
    colL=len(header_cols)
    
    # Adding one Extra Row for some tables which have TD and TH in TR
    Matrix = [[0 for x in range(colL)] for y in range(rowL)] 
        
    currRowL=0
    currColL=0
    
    for row in table.findAll("tr"):
        cells = row.findAll(["th", "td"])

        for index, cell in enumerate(cells):
            #lots of cells span cols and rows so lets deal with that
            cspan=int(cell.get('colspan',1))
            rspan=int(cell.get('rowspan',1))   
            
            #Lets Go fill
            for i in range(cspan):
                for j in range(rspan):
                    tempCount=0
                    # Till you find a Not null column
                    
                    if (j+currRowL < rowL) & (i+currColL+tempCount < colL):
                        
                        while (Matrix[j+currRowL][i+currColL+tempCount] !=0):
                            tempCount+=1
                    
                        matOut = getLinkandValue(cell)
                        Matrix[j+currRowL][i+currColL+tempCount]= matOut
                    
                    
            currColL=currColL+cspan
            
            cspan=0
            rspan=0
            
        currRowL+=1
        currColL=0

    matDF=pd.DataFrame(Matrix)
    matDF.to_csv(filepath)

def getYearLevelMovie(langTemplates,wikiTemplates,yearly_dir):

    for timeframe,wikiTemp in wikiTemplates.items():
        for langKey, langValue in langTemplates.items():

            # Decade or Yearly 
            yearInc = 10 if timeframe == "Decade" else 1

            # Years 1900s to 2020s
            for year in range(1930,2020,yearInc):
                wikiURL = wikiTemp.replace("YYYY",str(year))
                wikiURL = wikiURL.replace("XXXX",str(langValue))

                try:
                    outputDir = yearly_dir.replace('{LANG}',langValue)
                    outputDir = outputDir + timeframe + "_" + str(year)
                    scrape(url=wikiURL,output_folder=outputDir,filetemplate=langValue,tabletype="wikitable")
                    print ("Scrapped ",outputDir)                
                except:
                    print ("Error Scrapping ",outputDir)
                    pass
    return True

# Combine all the files into a single file.. Figure out movies from the files that were downloaded

def combineAllYearLevelMovie(langTemplates,yearly_dir):

    finalFileList = []

    # Algorithm to identify which is a legitimate movie table and which are not in wikipedia
    for path, subdirs, files in os.walk(yearly_dir):
        for fname in files:
            if ".csv" in fname:
                tableFile = os.path.join(path, fname)
                tableDF = pd.read_csv(tableFile)

                # headerVal is used to seggregate actual movie tables from other related tables. Header needs to be >= 2.5
                headerVal = 0
                for name, values in tableDF.iloc[0].iteritems():
                    try:
                        values = ast.literal_eval(values)
                        checkHeader = (next(iter(values)))
                        if checkHeader in ['Opening','Title','Director','Cast','Rank','Movie']:
                            if checkHeader in ['Title','Director','Cast']:
                                headerVal+=1
                            elif checkHeader in ['Opening','Movie']:
                                headerVal = headerVal + .5
                            else:
                                headerVal-=2
                    except:
                        pass

                # 2.5 number seemed to be perfect fit after the penalization function in the previous step
                if headerVal >= 2.5:                
                    finalFileList.append(tableFile)

    allMovieColumns = ['EntityID','WikiLink','TableFilename','Language','Title','Director','Cast','Opening','Production','Music','Genre']
    dfMovieList = pd.DataFrame(columns=allMovieColumns)
    mapOldColstoNew = {"Music Director":"Music","Producer":"Production","Notes":"Production","Movie":"Title","Release Date":"Opening"}

    # Get files and upload to main Dataframe
    for file in finalFileList:
        tableDF = pd.read_csv(file)

        headerIndex = 0
        headerCurrent = []
        colsToAppend = []
        checkHeader = ""

        for name, values in tableDF.iloc[0].iteritems():
            try:
                values = ast.literal_eval(values)
                checkHeader = (next(iter(values)))

            except:
                checkHeader = values
                pass

            # If column is Dict , the column rename works but fails in merge/join/concat
            if isinstance(checkHeader, str) is False:
                checkHeader = headerIndex

            if checkHeader in headerCurrent:
                tableDF.columns.values[headerIndex] = checkHeader + str(headerIndex)
            else:
                tableDF.columns.values[headerIndex] = checkHeader

            headerCurrent.append(checkHeader)
            headerIndex+=1    

        tableDF['WikiLink'] = file
        tableDF['TableFilename'] = file
        tableDF['Language'] = file.split('/')[0]
        tableDF = tableDF.iloc[1:]

        # Rename columns to be consistent with Main file
        currtableDFColList = list(tableDF.columns.values)

        for col in currtableDFColList:
            if col in allMovieColumns:
                colsToAppend.append(col)
            value = mapOldColstoNew.get(col)
            if value is not None:
                tableDF.rename(columns={col: value}, inplace=True)
                colsToAppend.append(value)

        # Add missing columns as Pandas needs all columns to concat or append
        missingColList = (list(set(allMovieColumns) - set(colsToAppend)))
        for missingCol in missingColList:
            tableDF[missingCol] = ""
            colsToAppend.append(missingCol)

        # Append table to Main list
        dfMovieList = dfMovieList.append(tableDF[colsToAppend])
        
    # Append movie entity id
    dfMovieList = dfMovieList.reset_index()
    for index,row in dfMovieList.iterrows():
        dfMovieList.ix[index, 'EntityID'] = uuid.uuid4()

    return dfMovieList

def downloadYearlyData(lang):

    # Get Config info
    config_dir = 'configuration/'
    config_file = 'config.json'
    config = get_config(config_dir,config_file)

    langTemplates = {"Bengali":"Bengali","Hindi":"Bollywood","Gujarati":"Gujarati","Kannada":"Kannada","Malayalam":"Malayalam","Marathi":"Marathi","Punjabi":"Punjabi","Odia":"Ollywood","Tamil":"Tamil","Telugu":"Telugu"}
    langTemplates = {lang : langTemplates[lang]}
    wikiTemplates = {"Decade":"https://en.wikipedia.org/wiki/List_of_XXXX_films_of_the_YYYYs","Year":"https://en.wikipedia.org/wiki/List_of_XXXX_films_of_YYYY"}

    # Download all the wikipedia language and year level contents
    getYearLevelMovie(langTemplates,wikiTemplates,config['yearly_dir'])

    # Combine all years of data into movie level dataframe
    dfMovieList = combineAllYearLevelMovie(langTemplates,config['yearly_dir'].replace('{LANG}',lang))

    dfMovieList.to_csv(config['dataframe_dir'].replace('{LANG}',lang) + lang + "_movie_combined_yearly.csv")

    return

def main():
    return

if __name__ == '__main__':
    main()

