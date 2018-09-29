'''
 Code to extract all missing information from movie page and update the CSV file in Downloads/Dataframe folder
'''

import pandas as pd
import ast
import wiki_table_extract as wt
import numpy as np
import os
import re
import json
import wikipedia
from bs4 import BeautifulSoup
import requests

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

# function to get unordered list from Cast
def get_section_ol_list(url,sectiontitle,titleWiki,fileName,titleYear,entityID):

    resp = requests.get(url)
    soup = BeautifulSoup(resp.content, 'lxml')
    # Added by Arun - Wikitable
    table_classes = {"class": ["mw-headline"],"id":[sectiontitle]}
    wikitables = soup.find("span",table_classes)

    ol_found = 0
    cast_list = []
    c_row_list = []
    
    # if Class of next element is H2 then quit,else search for OL tag,if OL tag is completed then quit
    if wikitables is not None:
        while wikitables.next_element: 
            wikitables = wikitables.next_element
            castName = ""
            castLink = ""
            castRole = ""
            cast_sublist = []

            if wikitables.name == "h2":     
                break
            elif wikitables.name == "ul":
                ol_found = 1
            elif ol_found == 1 and wikitables.name == "li":
                for index,item in enumerate(wikitables.contents):
                    if item.name == "a" and index ==0:
                        castName = item.string
                        cast_sublist.append(castName)
                        castLink = item.get("href")
                        cast_sublist.append(castLink)
                        #print (wt.getLinkandValue(item))
                    elif index == 0:
                        castName = item.string
                        cast_sublist.append(castName)
                        castLink = ""
                        cast_sublist.append(castLink)     
                    elif index == 1:
                        castRole = re.sub(r'([\(\[]).*?([\)\]])', '', item.string)
                        cast_sublist.append(castRole)                      
                cast_list.append(cast_sublist)
            pass

        # Put the castlist as a dictionary
        c_row_list = []

        for cindex,castItem in enumerate(cast_list):

            castdict = {}
            castdict['EntityID'] = entityID
            castdict['WikiTitleLink'] = titleWiki                            
            castdict['Title'] = fileName
            castdict['Year'] = titleYear                                        
            castdict['Role'] = "AllCast"
            castdict['Person'] = re.sub(r'([\(\[]).*?([\)\]])', '', castItem[0])
            if len(castItem) > 2:
                castdict['RoleAlias'] = castItem[2]
            else:
                castdict['RoleAlias'] = ""
            if len(castItem) > 1:
                castdict['PersonWikiLink'] = castItem[1]
            else:
                castdict['PersonWikiLink'] = ""
            # Rowlist to be appended
            c_row_list.append(castdict)
    
    return c_row_list

# Get movies based on indexes. index Range is between 1 to N ( N is the Thousanth digit )

def extract_missing_info(lang,indexRange):

	# Config file
	config_dir = 'configuration/'
	config_file = 'config.json'

	config = get_config(config_dir,config_file)

    # Get the file to be used.
    movieDFfile = config['dataframe_dir'].replace('{LANG}',lang) + lang + '_movie_combined_yearly.csv'
    infoboxDir = config['infobox_dir'].replace('{LANG}',lang)

    movieListDF = pd.read_csv(movieDFfile)

    allMovieEntityColumns = ['EntityID','WikiTitleLink','Language','Title','Year','ReleaseDate','Production','Budget','BoxOffice','Runtime']
    # Examples of Person [ Producer,Cast,Director, Music Director, Writters, Screenplay etc ]
    allMoviePersonColumns = ['EntityID','WikiTitleLink','Title','Year','Person','PersonWikiLink','Role','RoleAlias']
    # Examples of Key / Value pairs [ Plot, Summary, End Links ]
    allMovieTextColumns = ['EntityID','WikiTitleLink','Title','Year','Summary','OriginalPlot']

    personList = ['Directed by','Produced by','Written by','Story by','Screenplay by','Starring','Music by','Cinematography','Edited by']
    entityList = ['Release date','Running time','Productioncompany','Budget','BoxOffice']
    entityMaplist = {'Release date':'ReleaseDate','Running time':'Runtime','Productioncompany':'Production','Budget':'Budget','Box office':'BoxOffice'}

    # Data frame for different types of data
    dfMoviePerson = pd.DataFrame(columns=allMoviePersonColumns)
    dfEntityData = pd.DataFrame(columns=allMovieEntityColumns)
    dfTextData = pd.DataFrame(columns=allMovieTextColumns)

    # Iterrate over all the movies in the langauge and collect data from wiki links
    for index,row in movieListDF.iterrows():
        try:
            # Get the films in the 1000's
            if index >= ( ( indexRange - 1 ) * 1000 ) and index < ( indexRange * 1000 ):

                # collect basic info about the movie from the DF

                titleWikiDict = ast.literal_eval(row['Title'])
                titleWikiLink = (next (iter (titleWikiDict.values())))
                titleWiki = (next (iter (titleWikiDict.keys())))
                titleYear = row['TableFilename'].split('/')[3].split('_')[1]            
                fileName = str(titleYear) + '_' + list(titleWikiDict.keys())[0]
                entityID = row['EntityID']

                print (index,infoboxDir,fileName,entityID)

                # Save the infobox and get summary and plot from the Wiki

                if titleWikiLink.startswith('/wiki/'):
                    wikiURL = 'https://en.wikipedia.org' + titleWikiLink
                    wt.scrape(url=wikiURL,output_folder=infoboxDir,filetemplate=fileName,tabletype="infobox")

                    # Get Summary, Cast and Plot from the Wiki page
                    wikipage=wikipedia.WikipediaPage(titleWikiLink.replace('/wiki/',''))
                    wikiPlot = wikipage.section('Plot')
                    wikiSummary = wikipage.summary

                    text_list = []
                    textdict = {}
                    textdict['EntityID']=entityID
                    textdict['WikiTitleLink']=titleWikiLink
                    textdict['Title']=titleWiki
                    textdict['Year']=titleYear
                    textdict['OriginalPlot'] = wikiPlot
                    textdict['Summary'] = wikiSummary

                    # Rowlist to be appended
                    text_list.append(textdict)
                    dfTextData = dfTextData.append(text_list)                     

                    # Get All Cast from the Wiki page
                    c_row_list = get_section_ol_list(wikiURL,"Cast",titleWiki,fileName,titleYear,entityID)

                    if len(c_row_list) > 0:
                        dfMoviePerson = dfMoviePerson.append(c_row_list) 


                # Extract information from the Wiki page that was saved

                e_row_list = []
                entitydict = {}
                entitydict['EntityID']=entityID
                entitydict['WikiTitleLink']=titleWikiLink
                entitydict['Language']="Tamil"
                entitydict['Title']=titleWiki
                entitydict['Year']=titleYear
                entitydict['ReleaseDate']=""
                entitydict['Production']=""
                entitydict['Budget']=""
                entitydict['BoxOffice']="" 
                entitydict['Runtime']=""

                for directory, subdirectories, files in os.walk(infoboxDir):
                    for file in files:
                        if fileName in file:

                            tableFile = os.path.join(infoboxDir, file)
                            tableDF = pd.read_csv(tableFile)

                            # For each item in the infobox
                            for t_index,t_row in tableDF.iterrows():

                                # Try catch to ignore issues when {} and eval function fails. 
                                try:
                                    rowHeader = ast.literal_eval(t_row[1])

                                    # Boolean to test if the Dict is empty or not.
                                    if bool(rowHeader) is True:
                                        rowHeaderKey = (next (iter (rowHeader.keys())))
                                        rowValue = ast.literal_eval(t_row[2])

                                        # Dealing with multiple Keys. Eg. Muti starrer, multi director , writters
                                        for rowValueKey, rowValueLink in rowValue.items():

                                            if rowHeaderKey in personList:

                                                p_row_list = []
                                                persondict = {}
                                                persondict['EntityID']=entityID
                                                persondict['WikiTitleLink'] = titleWiki                            
                                                persondict['Title'] = fileName
                                                persondict['Year'] = titleYear                                        
                                                persondict['Role'] = rowHeaderKey
                                                persondict['RoleAlias'] = ""
                                                persondict['Person'] = re.sub(r'([\(\[]).*?([\)\]])', '', rowValueKey)
                                                persondict['PersonWikiLink'] = rowValueLink

                                                # Rowlist to be appended
                                                p_row_list.append(persondict)
                                                dfMoviePerson = dfMoviePerson.append(p_row_list) 

                                            elif rowHeaderKey in entityList:
                                                colName=entityMaplist[rowHeaderKey]
                                                # Removes () and [] from the text. Was in Date and links like [1]
                                                entitydict[colName]=re.sub(r'([\(\[]).*?([\)\]])', '', rowValueKey)
                                            else:
                                                # Do nothing ( there are other parameters that are not captured for now)
                                                pass

                                except:
                                    print (entityID,titleWikiDict, " Unable to get InfoBox details")
                                    pass

                e_row_list.append(entitydict)
                dfEntityData = dfEntityData.append(e_row_list) 

        except:
            print (entityID,titleWikiDict," Failed")
            pass


    # Save the dataframe
    
    dfMoviePerson.to_csv(config['dataframe_dir'].replace('{LANG}',lang) + lang + "_movie_persons" + str(indexRange) + ".csv")
    dfEntityData.to_csv(config['dataframe_dir'].replace('{LANG}',lang) + lang + "_movie_entities" + str(indexRange) + ".csv")
    dfTextData.to_csv(config['dataframe_dir'].replace('{LANG}',lang) + lang + "_movie_text_contents" + str(indexRange) + ".csv")

    return True

def main():
    return

if __name__ == '__main__':
    main()