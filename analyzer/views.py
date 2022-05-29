from django.shortcuts import render

# Create your views here.
import os
import json
import time
import csv
import pandas as pd
import re
from tqdm import tqdm
from time import sleep
from datetime import datetime
from analyzer.configuration_settings import times_calculation_mode, metadata_location, sep, decision_foldername
from featureextraction.views import check_npy_components_of_capture
from decisiondiscovery.views import decision_tree_training, extract_training_dataset
from featureextraction.views import gui_components_detection, classify_image_components
# CaseStudyView
from rest_framework import generics, status, viewsets #, permissions
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from .models import CaseStudy
from .serializers import CaseStudySerializer
from django.shortcuts import get_object_or_404
from django.utils import timezone


def get_foldernames_as_list(path, sep):
    folders_and_files = os.listdir(path)
    family_names = []
    for f in folders_and_files:
        if os.path.isdir(path+sep+f):
            family_names.append(f)
    return family_names

def generate_case_study(exp_foldername, exp_folder_complete_path, decision_activity, scenarios, to_exec):
    times = {}
    family_names = get_foldernames_as_list(exp_folder_complete_path + sep + scenarios[0], sep)
    exp_folder_complete_path + sep + "metadata" + sep
    metadata_path = metadata_location + sep + exp_foldername + "_metadata" + sep
    
    if not os.path.exists(metadata_path):
        os.makedirs(metadata_path)

    for scenario in tqdm(scenarios, desc="Scenarios that have been processed: "):
        sleep(.1)
        print("\nActual Scenario: " + str(scenario))
        param_path = exp_folder_complete_path + sep + scenario + sep
        if to_exec and len(to_exec) > 0:
            for n in family_names:
                times[n] = {}
                
                decision_tree_library           = to_exec['decision_tree_training']['library'] if (('decision_tree_training' in to_exec) and ('library' in to_exec['decision_tree_training'])) else 'sklearn'
                decision_tree_algorithms        = to_exec['decision_tree_training']['algorithms'] if (('decision_tree_training' in to_exec) and ('algorithms' in to_exec['decision_tree_training'])) else None # ['ID3', 'CART', 'CHAID', 'C4.5']
                decision_tree_mode              = to_exec['decision_tree_training']['mode'] if (('decision_tree_training' in to_exec) and ('mode' in to_exec['decision_tree_training'])) else 'autogeneration'
                decision_columns_to_ignore      = to_exec['decision_tree_training']['columns_to_ignore'] if (('decision_tree_training' in to_exec) and ('columns_to_ignore' in to_exec['decision_tree_training'])) else None
                training_columns_to_ignore      = to_exec['extract_training_dataset']['columns_to_ignore'] if (('extract_training_dataset' in to_exec) and ('columns_to_ignore' in to_exec['extract_training_dataset'])) else None

                to_exec_args = {
                    'gui_components_detection': (param_path+n+sep+'log.csv', 
                                                 param_path+n+sep, 
                                                 to_exec['gui_components_detection']['add_words_columns'],
                                                 to_exec['gui_components_detection']['gaze_analysis'],
                                                 to_exec['gui_components_detection']['overwrite_npy']),
                    'classify_image_components': ('resources'+sep+'models'+sep+'model.json',
                                                  'resources'+sep+'models'+sep+'model.h5',
                                                  param_path + n + sep + 'components_npy' + sep,
                                                  param_path+n+sep + 'log.csv',
                                                  param_path+n+sep+'enriched_log.csv',
                                                  False),
                    'extract_training_dataset': (decision_activity, param_path + n + sep + 'enriched_log.csv', param_path + n + sep, training_columns_to_ignore),
                    'decision_tree_training': (param_path+n+sep + 'preprocessed_dataset.csv', param_path+n+sep, decision_tree_library, decision_tree_mode, decision_tree_algorithms, decision_columns_to_ignore) # 'autogeneration' -> to plot tree automatically
                    }
                
                for function_to_exec in to_exec.keys():
                    if function_to_exec == "decision_tree_training" and decision_tree_library!='sklearn':
                        res, tree_times = eval(function_to_exec)(*to_exec_args[function_to_exec])
                        times[n][function_to_exec] = tree_times
                    else:
                        times[n][function_to_exec] = {"start": time.time()}
                        output = eval(function_to_exec)(*to_exec_args[function_to_exec])
                        times[n][function_to_exec]["finish"] = time.time()
                        
                    # TODO: accurracy_score
                    # if index == len(to_exec)-1:
                    #     times[n][index]["decision_model_accuracy"] = output

            # if not os.path.exists(scenario+sep):
            #     os.makedirs(scenario+sep)

            # Serializing json
            json_object = json.dumps(times, indent=4)
            # Writing to .json
            with open(metadata_path+scenario+"-metainfo.json", "w") as outfile:
                outfile.write(json_object)
    # cada experimento una linea: csv
    # almaceno los tiempos por cada fase y por cada experimento (por cada familia hay 30)
    # ejecutar solamente los experimentos


def times_duration(times_dict):
    if times_calculation_mode == "formatted":
        format = "%H:%M:%S.%fS"
        difference = datetime.strptime(times_dict["finish"], format) - datetime.strptime(times_dict["start"], format)
        res = difference.total_seconds()
    else:
        res = float(times_dict["finish"]) - float(times_dict["start"])
    return res


def calculate_accuracy_per_tree(decision_tree_path, expression, quantity_difference, algorithm):
    res = {}
    # This code is useful if we want to get the expresion like: [["TextView", "B"],["ImageView", "B"]]
    # if not isinstance(levels, list):
    #     levels = [levels]
    levels = expression.replace("(", "")
    levels = levels.replace(")", "")
    levels = levels.split(" ")
    for op in ["and","or"]:
      while op in levels:
        levels.remove(op)

    if not algorithm:
        f = open(decision_tree_path + "decision_tree.log", "r").read()
        for gui_component_name_to_find in levels:
        # This code is useful if we want to get the expresion like: [["TextView", "B"],["ImageView", "B"]]
        # for gui_component_class in levels:
            # if len(gui_component_class) == 1:
            #     gui_component_name_to_find = gui_component_class[0]
            # else:
            #     gui_component_name_to_find = gui_component_class[0] + \
            #         "_"+gui_component_class[1]
            position = f.find(gui_component_name_to_find)
            res[gui_component_name_to_find] = "False"
            if position != -1:
                positions = [m.start() for m in re.finditer(gui_component_name_to_find, f)]
                number_of_nodes = int(len(positions)/2)
                if len(positions) != 2:
                    print("Warning: GUI component appears more than twice")
                for n_nod in range(0, number_of_nodes):
                    res_partial = {}
                    for index, position_i in enumerate(positions):
                        position_i += 2*n_nod
                        position_aux = position_i + len(gui_component_name_to_find)
                        s = f[position_aux:]
                        end_position = s.find("\n")
                        quantity = f[position_aux:position_aux+end_position]
                        for c in '<>= ':
                            quantity = quantity.replace(c, '')
                            res_partial[index] = quantity
                    if float(res_partial[0])-float(res_partial[1]) > quantity_difference:
                        print("GUI component quantity difference greater than the expected")
                        res[gui_component_name_to_find] = "False"
                    else:
                        res[gui_component_name_to_find] = "True"
    else:
        json_f = open(decision_tree_path + decision_foldername + sep + algorithm + "-rules.json")
        decision_tree_decision_points = json.load(json_f)
        for gui_component_name_to_find in levels:
            # res_partial = []
            # gui_component_to_find_index = 0
            res_aux = False
            for node in decision_tree_decision_points:
                res_aux = res_aux or (node['return_statement'] == 0 and ('x0_'+gui_component_name_to_find in node['feature_name']))
                    # return_statement: filtering return statements (only conditions evaluations)
                    # feature_name: filtering feature names as the ones contained on the expression
            #         feature_complete_id = 'obj['+str(node['feature_idx'])+']'
            #         pos1 = node['rule'].find(feature_complete_id) + len(feature_complete_id)
            #         pos2 = node['rule'].find(':')
            #         quantity = node['rule'][pos1:pos2]
            #         res_partial.append(quantity)
            #         for c in '<>= ':
            #             quantity = quantity.replace(c, '')
            #             res_partial[gui_component_to_find_index] = quantity
            #         gui_component_to_find_index +=1
            # if res_partial and len(res_partial) == 2:
            #     res_aux = (float(res_partial[0])-float(res_partial[1]) <= quantity_difference)
            #     if not res_aux:
            #         print("GUI component quantity difference greater than the expected: len->" + str(len(res_partial)))
            # else:
            #     res_aux = False
            res[gui_component_name_to_find] = str(res_aux)

    s = expression
    print(res)
    for gui_component_name_to_find in levels:
        s = s.replace(gui_component_name_to_find, res[gui_component_name_to_find])
    
    res = eval(s)
        
    if not res:
      print("Condition " + str(expression) + " is not fulfilled")
    return int(res)


def experiments_results_collectors(exp_foldername, exp_folder_complete_path, scenarios, gui_component_class, quantity_difference, decision_tree_filename, phases_to_execute, drop):
    csv_filename = exp_folder_complete_path + sep + exp_foldername + "_results.csv"

    times_info_path = metadata_location + sep + exp_foldername + "_metadata" + sep
    preprocessed_log_filename = "preprocessed_dataset.csv"

    # print("Scenarios: " + str(scenarios))
    family = []
    balanced = []
    log_size = []
    scenario_number = []
    log_column = []
    phases_info = {}
    # detection_time = []
    # classification_time = []
    # flat_time = []
    # tree_training_time = []
    # tree_training_accuracy = []
    
    decision_tree_algorithms = phases_to_execute['decision_tree_training']['algorithms'] if (('decision_tree_training' in phases_to_execute) and ('algorithms' in phases_to_execute['decision_tree_training'])) else None

    if decision_tree_algorithms:
        accuracy = {}
    else:
        accuracy = []
        
    for scenario in tqdm(scenarios,
                         desc="Experiment results that have been processed"):
        sleep(.1)
        scenario_path = exp_folder_complete_path + sep + scenario
        family_size_balance_variations = get_foldernames_as_list(
            scenario_path, sep)
        if drop and drop in family_size_balance_variations:
            family_size_balance_variations.remove(drop)
        json_f = open(times_info_path+scenario+"-metainfo.json")
        times = json.load(json_f)
        for n in family_size_balance_variations:
            metainfo = n.split("_")
            # path example of decision tree specification: agosuirpa\CSV_exit\resources\version1637144717955\scenario_1\Basic_10_Imbalanced\decision_tree.log
            decision_tree_path = scenario_path + sep + n + sep
            
            with open(scenario_path + sep + n + sep + preprocessed_log_filename, newline='') as f:
                csv_reader = csv.reader(f)
                csv_headings = next(csv_reader)
            log_column.append(len(csv_headings))

            family.append(metainfo[0])
            log_size.append(metainfo[1])
            scenario_number.append(scenario.split("_")[1])
            # 1 == Balanced, 0 == Imbalanced
            balanced.append(1 if metainfo[2] == "Balanced" else 0)
            
            for phase in phases_to_execute.keys():
                if not (phase == 'decision_tree_training' and decision_tree_algorithms):
                    if phase in phases_info:
                        phases_info[phase].append(times_duration(times[n][phase]))
                    else:
                        phases_info[phase] = [times_duration(times[n][phase])]
                
            # TODO: accurracy_score
            # tree_training_accuracy.append(times[n]["3"]["decision_model_accuracy"])

            if decision_tree_algorithms:
                for alg in decision_tree_algorithms:
                    if (alg+'_accuracy') in accuracy:
                        accuracy[alg+'_tree_training_time'].append(times_duration(times[n]['decision_tree_training'][alg]))
                        accuracy[alg+'_accuracy'].append(calculate_accuracy_per_tree(decision_tree_path, gui_component_class, quantity_difference, alg))
                    else:
                        accuracy[alg+'_tree_training_time'] = [times_duration(times[n]['decision_tree_training'][alg])]
                        accuracy[alg+'_accuracy'] = [calculate_accuracy_per_tree(decision_tree_path, gui_component_class, quantity_difference, alg)]
            else:
                # Calculate level of accuracy
                accuracy.append(calculate_accuracy_per_tree(decision_tree_path, gui_component_class, quantity_difference, None))
    
    dict_results = {
        'family': family,
        'balanced': balanced,
        'log_size': log_size,
        'scenario_number': scenario_number,
        'log_column': log_column,
        # TODO: accurracy_score
        # 'tree_training_accuracy': tree_training_accuracy,
    }
    
    
    if isinstance(accuracy, dict):
        for sub_entry in accuracy.items():
            dict_results[sub_entry[0]] = sub_entry[1]
    
    for phase in phases_info.keys():
        dict_results[phase] = phases_info[phase]

    df = pd.DataFrame(dict_results)
    df.to_csv(csv_filename)
    
    return csv_filename

# ========================================================================
# RUN CASE STUDY
# ========================================================================

# EXAMPLE JSON REQUEST BODY
# {
#     "title": "Test Case Study",
#     "mode": "results",
#     "exp_foldername": "Advanced_10_30",
#     "phases_to_execute": {
#         "extract_training_dataset": {
#             "columns_to_ignore": ["Coor_X", "Coor_Y"]
#         },
#         "decision_tree_training": {
#             "library": "chefboost",
#             "algorithms": ["ID3", "CART", "CHAID", "C4.5"],
#             "mode": "autogeneration",
#             "columns_to_ignore": ["Timestamp_start", "Timestamp_end"]
#         }
#     },
#     "decision_point_activity": "B",
#     "exp_folder_complete_path": "C:\\Users\\Antonio\\Desktop\\caise data\\Advanced_10_30",
#     "gui_class_success_regex": "CheckBox_B or ImageView_B or TextView_B",
#     "gui_quantity_difference": 1,
#     "scenarios_to_study": null,
#     "drop": null
# }

def case_study_generator(mode, exp_foldername, phases_to_execute, decision_point_activity, exp_folder_complete_path, gui_class_success_regex, gui_quantity_difference, scenarios_to_study, drop):
    # =================================
    # Example values
    # version_name = "Advanced_10_30"
    # mode = "generation"
    # decision_point_activity = "D"
    # path_to_save_experiment = None
    # gui_class_success_regex = "CheckBox_D or ImageView_D or TextView_D" # "(CheckBox_D or ImageView_D or TextView_D) and (ImageView_B or TextView_B)"
    # gui_quantity_difference = 1
    # drop = None  # Example: ["Advanced_10_Balanced", "Advanced_10_Imbalanced"]
    # interactive = False
    # phases_to_execute = {'gui_components_detection': {},
    #                'classify_image_components': {},
    #                'extract_training_dataset': {},
    #                'decision_tree_training': {}
    #                }
    # scenarios = None # ["scenario_10","scenario_11","scenario_12","scenario_13"]
    
    # =================================
    # TODO: Expected results ## EXAMPLE: [["Case"],["ImageView", "D"]]
    # It is necessary to specify first the name of the GUI component and next the activity where iit takes place
    # In case of other column, you must specify only its name: for example ["Case"]
    
    msg = exp_foldername + ' not executed'
    executed = False
    
    if not scenarios_to_study:
        scenarios_to_study = get_foldernames_as_list(exp_folder_complete_path, sep)
        
    if mode == "generation" or mode == "both":
        generate_case_study(exp_foldername, exp_folder_complete_path, decision_point_activity, scenarios_to_study, phases_to_execute)
        msg = exp_foldername + ' case study generated!'
        executed = True
    if mode == "results" or mode == "both":
        # if exp_folder_complete_path and exp_folder_complete_path.find(sep) == -1:
        #     exp_folder_complete_path = exp_folder_complete_path + sep
        
        experiments_results_collectors(exp_foldername,
                                       exp_folder_complete_path,
                                       scenarios_to_study,
                                       gui_class_success_regex,
                                       gui_quantity_difference, 
                                       "decision_tree.log",
                                       phases_to_execute,
                                       drop)
        msg = exp_foldername + ' case study results collected!'
        executed = True
    
    return msg, executed

# ========================================================================
# RUN CASE STUDY (Legacy terminal mode)
# ========================================================================

def interactive_terminal(phases_to_execute, gui_class_success_regex, gui_quantity_difference, scenarios_to_study, drop):
    exp_foldername = input(
            'Enter the name of the folder generated by AGOSUIRPA with your experiment data (enter "UTILS" to check utilities): ')
    if exp_foldername != "UTILS":
        decision_point_activity = input(
            'Enter the activity immediately preceding the decision point you wish to study: ')
        mode = input(
            'Enter if you want to obtain experiment "generation", "results" or "both": ')

        if(mode in 'generation results both'):
            if mode == "results" or mode == "both":
                input_exp_path = input(
                    'Enter path where you want to store experiment results (if nothing typed, it will be stored in "media/"): ')
                path_to_save_experiment = input_exp_path if input_exp_path != "" else None

            case_study_generator(phases_to_execute, mode, scenarios_to_study, exp_foldername, path_to_save_experiment,
                                     decision_point_activity, gui_class_success_regex,
                                     gui_quantity_difference, None, drop)
        else:
            print('Please enter valid input')
    else:
        check_npy_components_of_capture(None, None, True)
        
        
class CaseStudyView(generics.ListCreateAPIView):
    # permission_classes = [IsAuthenticatedUser]
    serializer_class = CaseStudySerializer

    def get_queryset(self):
        return CaseStudy.objects.filter(shopper=self.request.user)

    def post(self, request, *args, **kwargs):
        case_study_serialized = CaseStudySerializer(data=request.data)
        st = status.HTTP_200_OK

        if not case_study_serialized.is_valid():
            response_content = case_study_serialized.errors
            st=status.HTTP_400_BAD_REQUEST
        else:
            execute_case_study = True
            try:
                if not isinstance(case_study_serialized.data['phases_to_execute'], dict):
                    response_content = {"message": "phases_to_execute must be of type dict!!!!! and must be composed by phases contained in ['gui_components_detection','classify_image_components','extract_training_dataset','decision_tree_training']"}
                    st = status.HTTP_422_UNPROCESSABLE_ENTITY 
                    execute_case_study = False
                    return Response(response_content, status=st)
                        
                for phase in dict(case_study_serialized.data['phases_to_execute']).keys():
                    if not(phase in ['gui_components_detection','classify_image_components','extract_training_dataset','decision_tree_training']):
                        response_content = {"message": "phases_to_execute must be composed by phases contained in ['gui_components_detection','classify_image_components','extract_training_dataset','decision_tree_training']"}
                        st = status.HTTP_422_UNPROCESSABLE_ENTITY 
                        execute_case_study = False
                        return Response(response_content, status=st)
                if execute_case_study:
                    generator_msg, generator_success = case_study_generator(
                                        case_study_serialized.data['mode'],
                                        case_study_serialized.data['exp_foldername'],
                                        case_study_serialized.data['phases_to_execute'],
                                        case_study_serialized.data['decision_point_activity'],
                                        case_study_serialized.data['exp_folder_complete_path'],
                                        case_study_serialized.data['gui_class_success_regex'],
                                        case_study_serialized.data['gui_quantity_difference'],
                                        case_study_serialized.data['scenarios_to_study'],
                                        case_study_serialized.data['drop']
                                        )
                    response_content = {"message": generator_msg}
                    if not generator_success:
                        st = status.HTTP_422_UNPROCESSABLE_ENTITY 
            except Exception as e:
                response_content = {"message": "Some of atributes are invalid: " + str(e) }
                st = status.HTTP_422_UNPROCESSABLE_ENTITY 
            
        # item = CaseStudy.objects.create(serializer)
        # result = CaseStudySerializer(item)
        # return Response(result.data, status=status.HTTP_201_CREATED)

        return Response(response_content, status=st)