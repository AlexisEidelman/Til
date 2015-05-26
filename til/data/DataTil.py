# -*- coding:utf-8 -*-
'''
Created on 22 juil. 2013
Alexis Eidelman
'''

#TODO: duppliquer la table avant le matching parent enfant pour ne pas se trimbaler les valeur de hod dans la duplication.

import numpy as np
import os
import tables

from pandas import merge, notnull, DataFrame, concat, HDFStore
import pkg_resources
import pdb

from til.data.utils.utils import replicate, new_link_with_men, of_name_to_til, new_idmen, count_dup


path_model = os.path.join(
    pkg_resources.get_distribution("Til-BaseModel").location,
    "til_base_model",
    )

# Dictionnaire des variables, cohérent avec les imports du modèle.
# il faut que ce soit à jour. Le premier éléments est la liste des
# entiers, le second celui des floats
variables_til = {
    'individus': (
        ['age_en_mois', 'sexe', 'idmen', 'quimen', 'idfoy', 'quifoy', 'tuteur', 'pere', 'mere', 'partner', 'civilstate',
         'findet', 'workstate', 'xpr', 'anc'],
        ['salaire_imposable', 'rsti', 'choi', 'tauxprime']
        ),
    'menages': (
        ['pref'],
        []
        ),
    'foyers_fiscaux': (
        ['vous', 'men'],
        []
        ),
    'futur': (
        ['age_en_mois', 'sexe', 'idmen', 'quimen', 'idfoy', 'quifoy', 'pere', 'mere', 'partner', 'civilstate', 'findet',
            'workstate', 'xpr', 'anc', 'deces'],
        ['salaire_imposable', 'rsti', 'choi']
        ),
    'past': (
        [],
        []
        )
    }


class DataTil(object):
    """
    La classe qui permet de lancer le travail sur les données
    La structure de classe n'est peut-être pas nécessaire pour l'instant
    """
    def __init__(self):
        self.name = None
        self.survey_date = None
        self.entity_by_name = {}
        self.time_data_frame_by_name = {}  # past, futur
        self.longitudinal = {}
        self.child_out_of_house = None
        self.seuil = None

        # TODO: Faire une fonction qui chexk où on en est, si les précédent on bien été fait, etc.
        self.done = []
        self.order = []

    def load(self):
        print "début de l'importation des données"
        raise NotImplementedError()
        print "fin de l'importation des données"

    #def rename_var(self, [pe1e, me1e]):
        # TODO: fonction qui renomme les variables pour qu'elles soient au format liam
        # period, id, age_en_mois, age, sexe, men, quimen, foy quifoy pere, mere, partner, dur_in_couple, civilstate, workstate, salaire_imposable, findet

    def drop_variable(self, variables_by_entity_name=None, option='white'):
        '''
        - Si on variables_by_entity_name is not None, il doit avoir la forme table: [liste de variables],
        on retire alors les variable de la liste de la table nommée.
        - Sinon, on se sert de cette méthode pour faire la première épuration des données, on
         a deux options:
             - passer par la liste blanche ce que l'on recommande pour l'instant
             - passer par  liste noire.
        '''
        assert variables_by_entity_name is not None
        for entity_name, variables in variables_by_entity_name.iteritems():
            data_frame = self.entity_by_name[entity_name]
            data_frame = data_frame.drop(variables, axis=1)

    def format_initial(self):
        raise NotImplementedError()

    def enfants(self):
        '''
        Calcule l'identifiant des parents
        '''
        raise NotImplementedError()

    def table_initial(self):
        raise NotImplementedError()

    def creation_foy(self):
        '''
        Créer les déclarations fiscale. Il s'agit principalement de regrouper certains individus entre eux.
        Ce n'est qu'ici qu'on s'occupe de verifier que les individus mariés ou pacsé ont le même statut matrimonial
        que leur partenaire légal. On ne peut pas le faire dès le début parce qu'on a besoin du numéro du partneroint.
        '''
        individus = self.entity_by_name['individus']
        menages = self.entity_by_name['menages']

        survey_date = self.survey_date
        print ("Creation des declarations fiscales")
        # 0eme étape: création de la variable 'nb_enf' si elle n'existe pas +  ajout 'lienpref'
        if 'nb_enf' not in individus.columns:
            # nb d'enfant
            individus.index = individus['id']
            nb_enf_mere = individus.groupby('mere').size()
            nb_enf_pere = individus.groupby('pere').size()
            # On assemble le nombre d'enfants pour les peres et meres en enlevant les manquantes (= -1)
            enf_tot = concat([nb_enf_mere, nb_enf_pere], axis=0)
            enf_tot = enf_tot.drop([-1])
            individus['nb_enf'] = 0
            individus['nb_enf'][enf_tot.index] = enf_tot.values

        def _name_var(individus_, menages_):
            if 'lienpref' in individus_.columns:
                individus_['quimen'] = individus_['lienpref']
                individus_.loc[individus_['quimen'] > 1, 'quimen'] = 2
                # a changer avec values quand le probleme d'identifiant et résolu .values
                menages_['pref'] = individus_.loc[individus_['lienpref'] == 0, 'id'].values
            return menages_, individus_

        menages, individus = _name_var(individus, menages)

        # 1ere étape: Identification des personnes mariées/pacsées
        spouse = (individus['partner'] != -1) & individus['civilstate'].isin([1, 5])
        print str(sum(spouse)) + " personnes en couples"

        # 2eme étape: rôles au sein du foyer fiscal
        # selection du partneroint qui va être le vousrant (= déclarant principal du foyer fiscal): pas d'incidence en théorie
        foyers_fiscaux = spouse & (individus['partner'] > individus['id'])
        partner = spouse & (individus['partner'] < individus['id'])
        # Identification des personnes à charge (moins de 21 ans sauf si étudiant, moins de 25 ans )
        # attention, on ne peut être à charge que si on n'est pas soi-même parent
        pac_condition = (individus['civilstate'] == 2) & (
            (
                (individus['age_en_mois'] < 12 * 25) & (individus['workstate'] == 11)
                ) |
            (individus['age_en_mois'] < 12 * 21)
            ) & \
            (individus['nb_enf'] == 0)
        pac = ((individus['pere'] != -1) | (individus['mere'] != -1)) & pac_condition
        print str(sum(pac)) + ' personnes prises en charge'
        # Identifiants associés
        individus['quifoy'] = 0
        individus.loc[partner, 'quifoy'] = 1
        # Comprend les enfants n'ayant pas de parents spécifiés (à terme rattachés au foyer 0= DASS)
        individus.loc[pac, 'quifoy'] = 2
        individus.loc[(individus['idmen'] == 0) & (individus['quifoy'] == 0), 'quifoy'] = 2
        print "Nombres de foyers fiscaux", sum(individus['quifoy'] == 0), ", dont couple", sum(individus['quifoy'] == 1)

        # 3eme étape: attribution des identifiants des foyers fiscaux
        individus['idfoy'] = -1
        nb_foy = sum(individus['quifoy'] == 0)
        print "Le nombre de foyers créés est: " + str(nb_foy)
        # Rq: correspond au même décalage que pour les ménages (10premiers: institutions)
        individus.loc[individus['quifoy'] == 0, 'idfoy'] = range(10, nb_foy + 10)

        # 4eme étape: Rattachement des autres membres du ménage
        # (a) - Rattachements des partneroints des personnes en couples
        partner = individus.loc[
            (individus['partner'] != -1) & (individus['civilstate'].isin([1, 5])) & (individus['quifoy'] == 0),
            ['partner', 'idfoy']
            ]
        individus['idfoy'][partner['partner'].values] = partner['idfoy'].values

        # (b) - Rattachements de leurs enfants (en priorité sur la décla du père)
        for parent in ['pere', 'mere']:
            pac_par = individus.loc[
                (individus['quifoy'] == 2) & (individus[parent] != -1) & (individus['idfoy'] == -1), ['id', parent]
                ].astype(int)
            individus['idfoy'][pac_par['id'].values] = individus['idfoy'][pac_par[parent].values]
            print str(len(pac_par)) + " enfants sur la déclaration de leur " + parent

        # Enfants de la Dass -> foyer fiscal 'collectif'
        individus.loc[individus['idmen'] == 0, 'idfoy'] = 0

        # 5eme étape: création de la table foy
        vous = (individus['quifoy'] == 0) & (individus['idfoy'] > 9)
        foyers_fiscaux = individus.loc[vous, ['idfoy', 'id', 'idmen']]
        foyers_fiscaux = foyers_fiscaux.rename(columns={'idfoy': 'id', 'id': 'vous'})
        # Etape propre à l'enquete Patrimoine
        impots = ['zcsgcrds', 'zfoncier', 'zimpot', 'zpenaliv', 'zpenalir', 'zpsocm', 'zrevfin']
        var_to_declar = impots + ['pond', 'id', 'pref']
        foy_men = menages.loc[menages['pref'].isin(foyers_fiscaux['vous']), var_to_declar].fillna(0)
        foy_men = foy_men.rename(columns = {'id': 'idmen'})

        # hypothèse réparartition des élements à égalité entre les déclarations: discutable
        nb_foy_men = foyers_fiscaux.loc[foyers_fiscaux['menages'].isin(foy_men['idmen'].values)].groupby('idmen').size()
        if (nb_foy_men.max() > 1) & (foy_men['zimpot'].max() > 0):
            assert len(nb_foy_men) == len(foy_men)
            for var in impots:
                foy_men[var] = foy_men[var] / nb_foy_men
            foyers_fiscaux = merge(foyers_fiscaux, foy_men, on = 'men', how = 'left', right_index = True)
        foyers_fiscaux['period'] = survey_date

        # Ajouts des 'communautés' dans la table foyer
        for k in [0]:
            if sum(individus['idfoy'] == k) != 0:
                to_add = DataFrame([np.zeros(len(foyers_fiscaux.columns))], columns = foyers_fiscaux.columns)
                to_add['id'] = k
                to_add['vous'] = -1
                to_add['period'] = survey_date
                foyers_fiscaux = concat([foyers_fiscaux, to_add], axis = 0, ignore_index = True)

        foyers_fiscaux.index = foyers_fiscaux['id']
        assert sum(individus['idfoy'] == -1) == 0
        print 'Taille de la table foyers:', len(foyers_fiscaux)
        # fin de declar
        self.entity_by_name['foyers_fiscaux'] = foyers_fiscaux
        self.entity_by_name['individus'] = individus
        self.entity_by_name['menages'] = menages

        print("fin de la creation des declarations")

    def creation_child_out_of_house(self):
        '''
        Travail sur les liens parents-enfants.
        On regarde d'abord les variables utiles pour le matching
        '''
        raise NotImplementedError()

    def matching_par_enf(self):
        '''
        Matching des parents et des enfants hors du domicile
        '''
        raise NotImplementedError()

    def match_couple_hdom(self):
        '''
        Certaines personnes se déclarent en couple avec quelqu'un ne vivant pas au domicile, on les reconstruit ici.
        Cette étape peut s'assimiler à de la fermeture de l'échantillon.
        On séléctionne les individus qui se déclare en couple avec quelqu'un hors du domicile.
        On match mariés,pacsé d'un côté et sans contrat de l'autre. Dit autrement, si on ne trouve pas de partenaire à une personne mariée ou pacsé on change son statut de couple.
        Comme pour les liens parents-enfants, on néglige ici la possibilité que le partneroint soit hors champ (étrange, prison, casernes, etc).
        Calcul aussi la variable individus['nb_enf']
        '''
        raise NotImplementedError()

    def expand_data(self, seuil=150, nb_ligne=None):
        # TODO: add future and past
        '''
        Note: ne doit pas tourner après lien parent_enfant
        Cependant child_out_of_house doit déjà avoir été créé car on s'en sert pour la réplication
        '''
        self.seuil = seuil
        if seuil != 0 and nb_ligne is not None:
            raise Exception(
            "On ne peut pas à la fois avoir un nombre de ligne désiré et une valeur qui va determiner le nombre de ligne"
            )
        # TODO: on peut prendre le min des deux quand même...
        foyers_fiscaux = self.entity_by_name.get('foyers_fiscaux')
        individus = self.entity_by_name['individus']
        menages = self.entity_by_name['menages']
        par = self.child_out_of_house
        longit = self.longitudinal

        if par is None:
            print(
                "Notez qu'il est plus malin d'étendre l'échantillon après avoir fait les tables " \
                "child_out_of_house plutôt que de les faire à partir des tables déjà étendue"
                )

        if foyers_fiscaux is None:
            print(
                "C'est en principe plus efficace d'étendre après la création de la table foyer" \
                " mais si on veut rattacher les enfants (par exemple de 22 ans) qui ne vivent pas au" \
                " domicile des parents sur leur déclaration, il faut faire l'extension et la " \
                " fermeture de l'échantillon d'abord. Pareil pour les couples. ")
        min_pond = min(menages['pond'])
        target_pond = float(max(min_pond, seuil))

        # 1 - Réhaussement des pondérations inférieures à la pondération cible
        menages['pond'][menages.pond < target_pond] = target_pond
        # 2 - Calcul du nombre de réplications à effectuer
        menages['nb_rep'] = menages['pond'].div(target_pond)
        menages['nb_rep'] = menages['nb_rep'].round()
        menages['nb_rep'] = menages['nb_rep'].astype(int)

        # 3- Nouvelles pondérations (qui seront celles associées aux individus après réplication)
        menages['pond'] = menages['pond'].div(menages['nb_rep'])
        # TO DO: réflechir pondération des personnes en collectivité pour l'instant = 1
        menages.loc[menages['id'] < 10, 'pond'] = 1
        men_exp = replicate(menages)

        # pour conserver les 10 premiers ménages = collectivités
        men_exp['id'] = new_idmen(men_exp, 'id')

        if foyers_fiscaux is not None:
            foyers_fiscaux = merge(
                menages[['id', 'nb_rep']], foyers_fiscaux,
                left_on='id', right_on='idmen', how='right', suffixes=('_men', '')
                )
            foy_exp = replicate(foyers_fiscaux)
            foy_exp['idmen'] = new_link_with_men(foyers_fiscaux, men_exp, 'idmen')
        else:
            foy_exp = None

        if par is not None:
            par = merge(menages[['id', 'nb_rep']], par, left_on = 'id', right_on='idmen', how='inner', suffixes=('_men', ''))
            par_exp = replicate(par)
            par_exp['idmen'] = new_link_with_men(par, men_exp, 'idmen')
        else:
            par_exp = None

        individus = merge(
            menages[['id', 'nb_rep']].rename(columns = {'id': 'idmen'}), individus, on='idmen', how='right',
            suffixes = ('_men', '')
            )
        ind_exp = replicate(individus)
        # lien indiv - entités supérieures
        ind_exp['idmen'] = new_link_with_men(individus, men_exp, 'idmen')
        ind_exp['idmen'] += 10

        # liens entre individus
        tableB = ind_exp[['id_rep', 'id_ini']]
        tableB['id_index'] = tableB.index
#         ind_exp = ind_exp.drop(['pere', 'mere', 'partner'], axis=1)
        print("debut travail sur identifiant")

        def _align_link(link_name, table_exp):
            tab = table_exp[[link_name, 'id_rep']].reset_index()
            tab = tab.merge(tableB, left_on=[link_name,'id_rep'], right_on=['id_ini', 'id_rep'], how='inner').set_index('index')
            tab = tab.drop([link_name], axis=1).rename(columns={'id_index': link_name})
            table_exp[link_name][tab.index.values] = tab[link_name].values
#             table_exp.merge(tab, left_index=True,right_index=True, how='left', copy=False)
            return table_exp

        ind_exp = _align_link('pere', ind_exp)
        ind_exp = _align_link('mere', ind_exp)
        ind_exp = _align_link('partner', ind_exp)

        # TODO: add _align_link with 'pere' and 'mere' in child_out_ouf_house in order to swap expand
        # and creation_child_out_ouf_house, in the running order

        if foyers_fiscaux is not None:
            # le plus simple est de repartir des quifoy, cela change du men
            # la vérité c'est que ça ne marche pas avec ind_exp['idfoy'] = new_link_with_men(ind, foy_exp, 'idfoy')
            vous = (individus['quifoy'] == 0)
            partner = (individus['quifoy'] == 1)
            pac = (individus['quifoy'] == 2)
            individus.loc[vous, 'idfoy'] = range(sum(vous))
            individus.loc[partner, 'idfoy'] = individus.ix[individus['partner'][partner], ['idfoy']]
            pac_pere = pac & notnull(individus['pere'])
            individus.loc[pac_pere, 'idfoy'] = individus.loc[individus.loc[pac_pere, 'pere'], ['idfoy']]
            pac_mere = pac & ~notnull(individus['idfoy'])
            individus.loc[pac_mere, 'idfoy'] = individus.loc[individus.loc[pac_mere, 'mere'], ['idfoy']]

        for name, table in longit.iteritems():
            table = table.merge(ind_exp[['id_ini', 'id']], right_on='id', left_index=True, how='right')
            table.set_index('id', inplace=True)
            table.drop('id_ini', axis=1, inplace=True)
            self.longitudinal[name] = table

        assert sum(individus['id'] == -1) == 0
        self.child_out_of_house = par
        self.entity_by_name['menages'] = men_exp
        self.entity_by_name['individus'] = ind_exp
        self.entity_by_name['foyers_fiscaux'] = foy_exp
        self.drop_variable({'men': ['id_rep', 'nb_rep'], 'ind': ['id_rep']})

    def format_to_liam(self):
        '''
        On met ici les variables avec les bons codes pour achever le travail de DataTil
        On crée aussi les variables utiles pour la simulation
        '''
        foyers_fiscaux = self.entity_by_name['foyers_fiscaux']
        individus = self.entity_by_name['individus']
        menages = self.entity_by_name['menages']
        futur = self.time_data_frame_by_name['futur']
        past = self.time_data_frame_by_name['past']

        ind_men = individus.groupby('idmen')
        individus = individus.set_index('idmen')
        individus['nb_men'] = ind_men.size().astype(np.int)
        individus = individus.reset_index()

        ind_foy = individus.groupby('idfoy')
        individus = individus.set_index('idfoy')
        individus['nb_foy'] = ind_foy.size().astype(np.int)
        individus = individus.reset_index()

        if 'lienpref' in individus.columns:
            self.drop_variable({'individus': ['lienpref', 'anais', 'mnais']})

        for data_frame_dictonnary in [self.entity_by_name, self.time_data_frame_by_name]:
            for name, table in data_frame_dictonnary.iteritems():
                if table is not None:
                    vars_int, vars_float = variables_til[name]
                    for var in vars_int + ['id', 'period']:
                        if var not in table.columns:
                            table[var] = -1
                        table = table.fillna(-1)
                        table[var] = table[var].astype(np.int32)
                    for var in vars_float + ['pond']:
                        if var not in table.columns:
                            if var == 'pond':
                                table[var] = 1
                            else:
                                table[var] = -1
                        table = table.fillna(-1)
                        table[var] = table[var].astype(np.float64)
                    table = table.sort_index(by=['period', 'id'])

#        # In case we need to Add one to each link because liam need no 0 in index
#        if individus['id'].min() == 0:
#            links = ['id', 'pere', 'mere', 'partner', 'idfoy', 'men', 'pref', 'vous']
#            for table in [ind, men, foy, futur, past]:
#                if table is not None:
#                    vars_link = [x for x in table.columns if x in links]
#                    table[vars_link] += 1
#                    table[vars_link].replace(0,-1, inplace=True)

    def _check_links(self, individus):
        if individus is None:
            individus = self.entity_by_name['individus']
        to_check = individus[['id', 'age_en_mois', 'sexe', 'idmen', 'partner', 'pere', 'mere']]
        # age parent
        tab = to_check.copy()
        for lien in ['partner', 'pere', 'mere']:
            tab = tab.merge(to_check, left_on=lien, right_on='id', suffixes=('', '_' + lien), how='left', sort=False)
        tab.index = tab['id']
        diff_age_pere = (tab['age_en_mois_pere'] - tab['age_en_mois'])
        diff_age_mere = (tab['age_en_mois_mere'] - tab['age_en_mois'])

        try:
            assert diff_age_pere.min() > 12 * 14
            assert diff_age_mere.min() > 12 * 12.4
            # pas de probleme du partneroint
            assert sum(tab['id_pere'] == tab['id_partner']) == 0
            assert sum(tab['id_mere'] == tab['id_partner']) == 0
            assert sum(tab['id_mere'] == tab['id_pere']) == 0
            assert sum(tab['sexe_mere'] == tab['sexe_pere']) == 0
        except:
            pdb.set_trace()

            test = diff_age_pere < 0
            tab[test]
        # on va plus loin sur les partneroints pour éviter les frères et soeurs:
        tab_partner = tab.loc[tab['partner'] > -1].copy()
        tab_partner.replace(-1, np.nan, inplace=True)
        try:
            assert all((tab_partner['id'] == tab_partner['partner_partner']))  # Les couples sont réciproques
            assert sum(tab_partner['mere'] == tab_partner['mere_partner']) == 0  # pas de mariage entre frere et soeur
            assert sum(tab_partner['pere'] == tab_partner['pere_partner']) == 0
        except:
            test = tab_partner['pere'] == tab_partner['pere_partner']
            pdb.set_trace()

    def final_check(self):
        ''' Les checks sont censés vérifiés toutes les conditions
            que doit vérifier une base pour tourner sur Til '''
        individus = self.entity_by_name['individus']
        foyers_fiscaux = self.entity_by_name['foyers_fiscaux']
        menages = self.entity_by_name['menages']
        futur = self.time_data_frame_by_name['futur']
        past = self.time_data_frame_by_name['past']

        assert all(individus['workstate'].isin(range(1, 12)))
        assert all(individus['civilstate'].isin(range(1, 6)))

        # Foyers et ménages bien attribués
        assert sum((individus['idfoy'] == -1)) == 0
        assert sum((individus['idmen'] == -1)) == 0
        print "Nombre de personnes dans ménages ordinaires: ", sum(individus['idmen'] > 9)
        print "Nombre de personnes vivant au sein de collectivités: ", sum(individus['idmen'] < 10)

        # On vérifie qu'on a un et un seul qui = 0 et au plus un qui = 1 pour foy et men
        for entity_id, entity_role in [('idmen', 'quimen'), ('idfoy', 'quifoy')]:
            individus['qui0'] = (individus[entity_role] == 0).astype(int)
            individus['qui1'] = (individus[entity_role] == 1).astype(int)
            ind0 = individus[individus[entity_id] > 9].groupby(entity_id)  # on exclut les collectivités
            # on vérifie qu'on a un et un seul qui = 0
            assert ind0['qui0'].sum().max() == 1
            assert ind0['qui0'].sum().min() == 1
            # on vérifie qu'on a au plus un qui = 1
            assert ind0['qui1'].sum().max() == 1
            # on vérifie que les noms d'identité sont bien dans la table entity et réciproquement
            if entity_id == 'idmen':
                list_id = self.entity_by_name['menages']['id']
            elif entity_id == 'idfoy':
                list_id = self.entity_by_name['foyers_fiscaux']['id']

            assert individus[entity_id].isin(list_id).all()
            assert list_id.isin(individus[entity_id]).all()
            # si on est un 2

            # si on est quimen = 1 alors on a son partneroint avec soi
            qui1 = individus[entity_role] == 1
            partner = individus.loc[qui1, 'partner'].values
            partner_ent = individus.iloc[partner]
            partner_ent = partner_ent[entity_id]
            qui1_ent = individus.loc[qui1, entity_id]
            assert (qui1_ent == partner_ent).all()

        # Table futur bien construite
        if futur is not None:
            # -> On vérifie que persone ne nait pas dans le futur tout en étant présent dans les données intiales
            id_ini = individus[['id']]
            # 'naiss' != -1 <-> naissance
            id_futur = futur.loc[(futur['naiss'] != -1), ['id']]
            id_ok = concat([id_ini, id_futur], axis = 0)
            assert count_dup(id_ok, 'id') == 0
            assert len(futur[(futur['naiss'] <= self.survey_year) & (futur['naiss'] != -1)]) == 0
            if len(futur.loc[~futur['id'].isin(id_ok['id']), 'id']) != 0:
                pb_id = futur.loc[~(futur['id'].isin(id_ok['id'])), :].drop_duplicates('id')
                print ('Nombre identifants problématiques dans la table futur: ', len(pb_id))

            print(
                "Nombre de personnes présentes dans la base " + str(len(id_ok)) + " (" + str(len(id_ini)) +
                " initialement et " + str(len(id_futur)) + " qui naissent ensuite)"
                )

        for table in [individus, menages, foyers_fiscaux, futur]:
            if table is not None:
                test_month = table['period'] % 100
                assert all(test_month.isin(range(1, 13)))
                test_year = table['period'] // 100
                assert all(test_year.isin(range(1900, 2100)))

        for name, table in self.longitudinal.iteritems():
            cols = table.columns
            cols_year = [(col // 100 in range(1900, 2100)) for col in cols]
            cols_month = [(col % 100 in range(1, 13)) for col in cols]
            assert all(cols_year)
            assert all(cols_month)

        # check reciprocity:
        assert all(individus.loc[individus['civilstate'].isin([1, 5]), 'partner'] > -1)
        rec = individus.loc[individus['partner'] != -1, ['id', 'partner', 'civilstate']]
        rec = rec.merge(rec, left_on='id', right_on='partner', suffixes=('', '_c'))
        # 1- check reciprocity of partner
        assert all(rec['partner_c'] == rec['id'])
        assert all(
            rec.loc[rec['civilstate'].isin([1, 5]), 'civilstate'] ==
            rec.loc[rec['civilstate'].isin([1, 5]), 'civilstate_c']
            )
        self._check_links(individus)

    def _output_name(self, extension='.h5'):
        if self.seuil is None:
            name = self.name + extension
        else:
            name = self.name + '_next_' + str(self.seuil) + extension
        return os.path.join(path_model, name)

    def store_to_liam(self):
        '''
        Sauvegarde des données au format utilisé ensuite par le modèle Til
        Séléctionne les variables appelée par Til derrière
        Appelle des fonctions de Liam2
        '''
        path = self._output_name()
        h5file = tables.openFile(path, mode="w")

        entity_node = h5file.createGroup("/", "entities", "Entities")
        for entity_name in ['individus', 'foyers_fiscaux', 'menages', 'futur', 'past']:
            entity = self.entity_name.get(entity_name) \
                if self.entity_name.get(entity_name) is not None \
                else self.time_data_frame_by_name[entity_name]
            if entity is not None:
                entity = entity.fillna(-1)
                try:
                    ent_table = entity.to_records(index=False)
                except:
                    pdb.set_trace()
                dtypes = ent_table.dtype
                final_name = of_name_to_til[entity_name]
                try:
                    table = h5file.createTable(entity_node, final_name, dtypes, title="%s table" % final_name)
                    table.append(ent_table)
                except:
                    pdb.set_trace()
                table.flush()

                if entity_name == 'menages':
                    entity = entity.loc[entity['id'] > -1]
                    ent_table2 = entity[['pond', 'id', 'period']].to_records(index=False)
                    dtypes2 = ent_table2.dtype
                    table = h5file.createTable(entity_node, 'companies', dtypes2, title="'companies table")
                    table.append(ent_table2)
                    table.flush()
                if entity_name == 'individus':
                    ent_table2 = entity[['age_en_mois', 'sexe', 'pere', 'mere', 'id', 'findet', 'period']].to_records(
                        index = False)
                    dtypes2 = ent_table2.dtype
                    table = h5file.createTable(entity_node, 'register', dtypes2, title="register table")
                    table.append(ent_table2)
                    table.flush()
        h5file.close()

        # 3 - table longitudinal
        # Note: on conserve le format pandas ici
        store = HDFStore(path)
        for varname, table in self.longitudinal.iteritems():
            table['id'] = table.index
            store.append('longitudinal/' + varname, table)
        store.close()

    def store(self):
        path = self._output_name()
        for entity_name, data_frame in self.entity_by_name.iteritems():
            data_frame.to_hdf(path, 'entites/{}'.format(entity_name))

    def run_all(self):
        for method in self.methods_order:
            eval('self.' + method + '()')
