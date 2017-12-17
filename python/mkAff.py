import sqlite3
from datetime import datetime
from collections import Counter
import operator

db_PAA = '/localdata/u5798145/influencemap/paper.db'
db_Authors = '/localdata/common/authors_test.db'
db_key = '/localdata/u6363358/data/paperKeywords.db'
db_FName = '/localdata/u6363358/data/FieldOfStudy.db'


def removeCon(lst):
   if lst[-2] == ",":
       return lst[:-2] + ")"
   else: 
       return lst

def isSame(name1, name2):
   ls2 = name2.split(' ')
   ls1 = name1.split(' ')
   middle1 = ls1[1:-1]
   middle2 = ls2[1:-1]
   if ls2[-1] == ls1[-1]:
       if ls2[0] == ls1[0]:
           middleShort1 = ''
           middleShort2 = ''
           for char in middle1:
               middleShort1 = middleShort1 + char[0]
           for char in middle2:
               middleShort2 = middleShort2 + char[0]
           return (middleShort2 in middleShort1) or (middleShort1 in middleShort2)
       else:
           return False
   else:
      return False

   
def mostCommon(lst):
    return max(set(lst),key=lst.count)


def getField(pID):
    dbK = sqlite3.connect(db_key, check_same_thread = False)
    dbN = sqlite3.connect(db_FName, check_same_thread = False)
    curK = dbK.cursor()
    curFN = dbN.cursor()
    curK.execute(removeCon("SELECT FieldID FROM paperKeywords WHERE PaperID IN {}".format(tuple(pID))))
    res = list(map(lambda x: x[0],curK.fetchall()))
    if len(res) > 0:
         res = sorted(dict(Counter(res)).items(),key=operator.itemgetter(1),reverse=True)
         topThree = {}
         for i in res:
             if len(topThree) < 3:
                 topThree[i[0]] = i[1] #topthree contains {fieldID, numPaper}
             else: break
         curFN.execute(removeCon("SELECT FieldName, FieldID FROM FieldOfStudy WHERE FieldID IN {}".format(tuple(map(lambda x: x,topThree)))))
         output = list(map(lambda x: (x[0],topThree[x[1]]),curFN.fetchall())) 
         dbK.commit()
         dbN.commit()
         dbK.close()
         dbN.close()
         return output
    else:
         dbK.commit()
         dbN.commit()
         dbK.close()
         dbN.close()
         return []

def getPaperName(pID):
    dbPAA = sqlite3.connect(db_PAA, check_same_thread = False)
    curP = dbPAA.cursor()
    curP.execute(removeCon("SELECT paperTitle,publishedDate FROM papers WHERE paperID IN {}".format(tuple(pID))))
    title = curP.fetchall()
    date = ''
    currentT = ''
    for p in title:
       if compareDate(p[1],date): #if the current date is greater
           date = p[1]
           currentT = p[0]
    dbPAA.commit()
    dbPAA.close()
    return (currentT,date)

def compareDate(currentT, date):
    if currentT != '':
       if date != '':
          if currentT[:4] > date[:4]: 
              return True
          elif currentT[:4] == date[:4]:
              if currentT[5:7] > date[5:7]:
                   return True
              elif currentT[5:7] == date[5:7]:
                  if currentT[-2:] > date[-2:]:
                      return True
                  else: return False
              else: return False
          else: return False
       else: return True
    else: return False

def getAuthor(name):
    dbPAA = sqlite3.connect(db_PAA, check_same_thread = False)
    dbA = sqlite3.connect(db_Authors, check_same_thread = False)
    dbA.create_function("isSame",2,isSame)
    curP = dbPAA.cursor()
    curA = dbA.cursor()

    #Extracting al the authorID whose name matches

    allAuthor = []
    print("{} getting all the aID".format(datetime.now()))
    curA.execute("SELECT * FROM authors WHERE authorName LIKE + '%" + name.split(' ')[-1] + "%' AND " + "isSame(authorName," + "'" + name + "')")
    allAuthor = curA.fetchall()
    print("{} finished getting all the aID".format(datetime.now()))
   
    author = {} #authorID is the key and authorName is the value
    #print("{} matching the right name".format(datetime.now()))
    for a in allAuthor:
         author[a[0]] = a[1]
    #print("{} finished matching".format(datetime.now()))
    
    aID = list(author.keys())
    result = []
    print("{} getting all the (authorID, paperID, affiliationName)".format(datetime.now()))
    curP.execute(removeCon("SELECT authorID, paperID, affiliationNameOriginal FROM weightedPaperAuthorAffiliations WHERE authorID IN {}".format(tuple(aID))))
    result = curP.fetchall()

    aIDpIDDict = {}
    
 
    finalres = []
    
    #Putting the authorName into the tuples
    for tuples in result:
       finalres.append((author[tuples[0]],tuples[0],tuples[1],tuples[2]))

    #Getting the most frequently appeared affiliation
    tempres = []
    finalresult = []
   
    print("{} counting the number of paper published by an author".format(datetime.now()))
    for tuples in finalres:
        currentID = tuples[1]
        if currentID not in list(map(lambda x:x[1], tempres)):
            count = 0
            tep = []
            pID = []
            for tup in finalres:
                if tup[1] == currentID:
                    count += 1
                    pID.append(tup[-2]) #pID contains paperID
                    tep.append(tup[-1]) #tep contatins affiliationNameOriginal
            tep[:] = [x for x in tep if x != '']
            aIDpIDDict[currentID] = pID
            if len(tep) > 0:
                tempres.append((tuples[0],tuples[1],count,mostCommon(tep),pID))
            else:
                tempres.append((tuples[0],tuples[1],count,'',pID))
    
    tempres = sorted(tempres,key=lambda x: x[2],reverse=True)
    print("{} finish counting, getting the fieldName".format(datetime.now()))
   
    for tuples in tempres:
        recent = getPaperName(tuples[-1]) #a tuple (paperName, date)
        finalresult.append({'name':tuples[0],'authorID':tuples[1],'numpaper':tuples[2],'affiliation':tuples[3],'field':getField(tuples[4]),'recentPaper':recent[0],'publishedDate':recent[1]})
    print("{} done".format(datetime.now()))
    
    dbPAA.commit()
    dbA.commit()  
    dbPAA.close()
    dbA.close()
   
    for dic in finalresult:
        print(dic)
   
    return (finalresult,aIDpIDDict)  

# trial = getAuthor('stephen m blackburn')
