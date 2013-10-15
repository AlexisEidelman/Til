# -*- coding:utf-8 -*-
'''
Created on 11 septembre 2013

Ce programme :
- 

Input : 
Output :

'''

# 1- Importation des classes/librairies/tables nécessaires à l'importation des données de l'enquête Patrimoine

# Recup de ce dont on a besoin dans Patrimoine

from pgm.CONFIG import path_data_patr, path_til, path_data_destinie
from data.DataTil import DataTil

import pandas as pd
import numpy as np
import pandas.rpy.common as com
import rpy2.rpy_classic as rpy

from pandas import merge, notnull, DataFrame, Series, HDFStore
from numpy.lib.stride_tricks import as_strided
import pdb
import gc



class Destinie(DataTil):  
      
    def __init__(self):
        DataTil.__init__(self)
        self.name = 'Destinie'
        self.survey_date = 200901
        
        #TODO: Faire une fonction qui check où on en est, si les précédent on bien été fait, etc.
        #TODO: Dans la même veine, on devrait définir la suppression des variables en fonction des étapes à venir.
        self.done = []
        self.methods_order = ['lecture']
       
    def lecture(self):
        longueur_carriere = 106
        print "début de l'importation des données"
        # TODO: revoir le colnames de BioEmp : le retirer ?
        colnames = list(xrange(longueur_carriere)) 
        BioEmp = pd.read_table(path_data_destinie +'BioEmp2.txt', 
                               names=colnames, header=None, sep=';')
        BioFam = pd.read_table(path_data_destinie + 'BioFam.txt', sep=',',
                          header=None, names=['id','pere','mere','statut',
                                           'conj','enf1',"enf2",
                                           "enf3",'enf4','enf5','enf6']) 
        print "fin de l'importation des données"
        
    #def built_BioEmp(self):
        print "Début mise en forme BioEmp"
        # 1 - Mise en forme de BioEmp
# inutile car l'index est 
#déjà comme ça par défaut       BioEmp = pd.DataFrame(BioEmp,index=range(0,len(BioEmp),1))

        taille = len(BioEmp)/3
        selection0 = [3*x for x in range(taille)]
        selection1 = [3*x+1 for x in range(taille)]
        selection2 = [3*x+2 for x in range(taille)]
        ind = BioEmp.iloc[selection0]
        ind = ind.reset_index()
        ind = ind.rename(columns={0:'id', 1:'sexe', 2:'naiss', 3:'findet'})
        ind = ind[['id','sexe','naiss','findet']]

# j'avais mal compris...à effacer       
# ind = pd.concat([ind, BioEmp.iloc[selection1].reset_index(),
#                          BioEmp.iloc[selection2].reset_index()],
#                          axis=1)
#        ind.columns[5:(5+longueur_carriere)] = 
#        ind.columns[5:(5+longueur_carriere)] = \
#            ['statut_'+str(2009+x) for x in range(longueur_carriere)]
#        ind.columns[5:(5+longueur_carriere)] = \
#            ['statut_'+str(2009+x) for x in range(longueur_carriere)]
#        pdb.set_trace()
#        
#        
        
        index = BioEmp.index  # BioEmp['index'] crée une variable, alors qu'on en a pas besoin
        BioEmp['id'] = BioEmp['index']/3
        BioEmp['id'] = BioEmp['id'].astype(int)
        #BioEmp['test'] = BioEmp[1] -> on appelle les colonnes avec un format numérique du coup
        
        BioEmp['nb_ligne'] = BioEmp['index'] - 3*BioEmp['id']

        # 2 - Construction de la Table ind : table avec toutes les info de bases sur les individus (appariement entre enfants et parents avec BioFam sur cette table) et car avec les infos sur carrières
        ind = BioEmp[BioEmp['nb_ligne']==0]
        ind = ind.rename(columns={1 :'sexe', 2 : 'naiss', 3 : 'findet'})
        ind = ind.loc['id','sexe','naiss','findet']

        '''
        Le programme met pas mal de temps à tourner : le premier merge pourrait ertainement être évité en travaillant conjointement sur statut/salaire
        C'est pas le tocsv qui prend du temps ? 
        attention, normalement les trois apostrophes c'est pour la documentation, pas pour le commentaire
        
        car = BioEmp[BioEmp['nb_ligne']>0]
        car['index'] = car.index
        car.to_csv('test1.csv')
        car = car.set_index('id').stack().reset_index()
        car1 = car['index','']
        car = pd.melt(car, id_vars=['index'])
        car = car.sort('id')
        car = car.set_index('id') 
        car = car.rename(columns={'variable': 'code_année'})
        car.to_csv('test.csv')
        '''
        
        # 3 - Construction de la table stat (table intermédiaire) avec les status d'emploi
        stat = BioEmp[BioEmp['nb_ligne']==1][col]
        stat = stat.set_index('id').stack().reset_index()
        stat['index'] =stat.index
        stat = stat.rename(columns={ 'level_1': 'annee', 0:'statut'})
        stat = stat[['id','annee','statut','index']]
        #stat.to_csv('test_stat.csv') 
        
        # 4 - Construction de la table sal (table intermédiare) avec les salaires en emploi
        sal = BioEmp[BioEmp['nb_ligne']==2][col]
        sal = sal.set_index('id').stack().reset_index()
        sal['index'] =sal.index
        sal = sal.rename(columns={'level_1': 'annee', 0:'salaire'})
        sal = sal[['salaire','index']]
        #sal.to_csv('test_sal.csv')

        # 5 - Sortie de la table agrégée contenant les infos de BioEmp -> pers
        m1 = merge(stat, sal, on = 'index')
        m1 = m1[['id','annee','statut', 'salaire']]
        pers = merge(m1, ind, on='id')
        # pers.to_csv('test_merge.csv')
        # print np.max(pers['id']) -> Donne bien 71937 correpondant aux 71938 personnes de l'échantillon initiale
        pers = pers[['id','annee','statut','salaire','sexe','naiss','findet']]
        pers['annee'] = pers['annee'] + pers['naiss']
        pers['annee'] = pers['annee'].astype(int)
        pers['annee'] = pers['annee'].astype(str) + '01' # Pour conserver un format similaire au format date de Til
        pers['annee'] = pers['annee'].astype(float) # Plus facile pour manip
        # pers.to_csv('test_finish.csv')
        print "fin de la mise en forme de BioEmp"

    #def add_link(self):
        print "Début mise en forme BioFam"
        
        # 1 - Mise en forme de  BioFam
        BioFam = pd.DataFrame(BioFam,index=range(0,len(BioFam),1))
        BioFam['index'] = BioFam.index
        BioFam['index'] = BioFam['index'].astype(float)
        
        # 2 - Variable 'date de mise à jour'
        fin = BioFam[BioFam['id'].str.contains('Fin')] # donne tous les index limites
        fin = fin.reset_index()
        fin['annee'] = fin.index + 2009
        fin = fin[['index','annee']] 
        fin.to_csv('test_fin.csv')      
        
        #BioFam['annee'] = fin[]
        '''
        #creation des ménages 
               # faire une méthode plutôt
        men = pd.Series(range(len(ind)))  # ne marche pas je pense, je
               # séléctionner les gens qui ont un conjoint, puis un père, puis une mère avec un noi près du leur (moins de 10 disons). A chaque fois leur mettre l'ident de la personne concernée. Ca peut foirer s'il y a des cas vicieux (on vit avec sa mère mais aussi avec son conjoint) et il faudra faire une autre boucle mais ça m'interesse de savoir si ce cas existe. 
        ''' 
        
        print "Fin mise en forme BioFam"

import time
start = time.clock()
data = Destinie()
data.lecture()
#data.built_BioEmp()
