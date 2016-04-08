# -*- coding: utf-8 -*-

import datetime
import os
import shlex

import neronet.core

MANDATORY_FIELDS = set(['run_command_prefix', 'main_code_file'])
"""Set: Experiment fields required in every config.yaml"""

OPTIONAL_FIELDS = set(['parameters', 'parameters_format', 'outputs', 
                        'output_line_processor', 'output_file_processor', 
                        'plot', 'collection', 'required_files', 'conditions', 
                        'sbatch_args', 'custom_msg'])
"""Set: Fields that Neronet uses but are not necessary"""

AUTOMATIC_FIELDS = set(['path', 'time_created', 'time_modified', 
                        'states_info', 'cluster_id', 'warnings'])
"""Set: Contains all fields automatically generated by Neronet"""

class OutputReadError(Exception):
    """ Exception raised when output reading failed
    """
    pass

class PlotError(Exception):
    """ Exception raised when ploting failed
    """

class Experiment(object):
    """ 
    Attributes:
        experiment_id (str): Unique identifier to the experiment
        run_command_prefix (str): The run command of the experiment
        main_code_file (str): The code file to be run
        required_files (str): Other files required by the experiments
        logoutput (str): File where the experiment outputs information
        parameters (dict): The Experiment parameters
        parameters_format (str): The format of the experiment parameters
        collection (str): The collection the experiment is part of
        conditions (dict): Special condition for the experiment to do stuff
        state (list of tuples): The states of the experiment with timestamp
        cluster_id (str): The ID of the cluster where the experiment is run
        time_created (datetime): Timestamp of when the experiment was created
        time_modified (datetime): Timestamp of when the experiment was modified
        last
        path (str): Path to the experiment folder
    """

    class State:
        #none = 'none'
        defined = 'defined'
        submitted = 'submitted'
        submitted_to_kid = 'submitted_to_kid'
        lost = 'lost'
        terminated = 'terminated'
        running = 'running'
        finished = 'finished'

    def __init__(self, experiment_id, run_command_prefix, main_code_file,
                    path, parameters=None, parameters_format="", 
                    required_files=None, outputs=None, 
                    output_line_processor=None, output_file_processor=None, 
                    collection=None, custom_msg=None, plot=None, 
                    conditions=None, sbatch_args=None):
        now = datetime.datetime.now()
        fields = {'run_command_prefix': run_command_prefix,
                    'main_code_file': main_code_file,
                    'required_files': required_files if required_files else [],
                    'outputs': outputs,
                    'output_file_processor': output_file_processor,
                    'output_line_processor': output_line_processor,
                    'plot': plot,
                    'parameters': parameters,
                    'parameters_format': parameters_format,
                    'collection': collection if collection else \
                                        [os.path.basename(path)],
                    'conditions': conditions,
                    'sbatch_args': sbatch_args,
                    'path': path,
                    'time_created': now,
                    'time_modified': now,
                    'run_results': [],
                    'states_info': [(Experiment.State.defined, now)],
                    'cluster_id': None,
                    'warnings' : [],
                    'custom_msg': custom_msg if custom_msg else "" }
        #MAGIC: Creates the attributes for the experiment class
        self.__dict__['_fields'] = fields
        #super(Experiment, self).__setattr__('_fields', fields)
        super(Experiment, self).__setattr__('_experiment_id', experiment_id)
        
    def get_results_dir(self):
        """Returns the location of the directory of the latest experiment results
        """
        root = neronet.core.USER_DATA_DIR_ABS
        if self.state == Experiment.State.finished:
            return self.run_results[-1]
        return os.path.join(root, 'results', self.id)

    def get_output(self, filename):
        """Returns the output data of the output file as a dict

        Returns:
            dict: The output file as a dictionary

        Raises:
            OutputReadError: When reading of the output failed
        """
        data = None
        #Checks which output reader type is specified for the file type
        #Prefers processor that read the whole file
        for processor_type in ['output_file_processor',
                                'output_line_processor']:
            if not self._fields[processor_type] or \
                filename not in self._fields[processor_type]:
                continue
            #Constructs the output reader and arguments
            args = \
                shlex.split(self._fields[processor_type][filename])
            try:
                module_name = args[0]
                reader_name = args[1]
                reader_args = args[2:]
            except:
                raise OutputReadError("%s: couldn't parse %s arguments" % \
                                        (self.id, processor_type))
            try:
                reader = neronet.core.import_from(module_name, reader_name)
            except:
                raise OutputReadError("%s: couldn't import %s from %s" % \
                                        (self.id, module_name, reader_name))
            #Gets the location of the results folder. 
            #Changes when the experiment has finnished
            results_dir = self.get_results_dir()
            
            #Opens the output file and processes the output data
            with open(os.path.join(results_dir, filename), 'r') as f:
                if processor_type == 'output_file_processor':
                    try:
                        data = reader(f.read(), *reader_args)
                    except:
                        raise OutputReadError("%s: couldn't read %s with %s" \
                                        % (self.id, filename, reader_name))
                    if not isinstance(data, dict):
                        raise OutputReadError("%s: %s for %s didn't return a"
                                "dict" % (self.id, processor_type, filename))
                else:
                    data = {}
                    for line in f:
                        try:
                            line_data = reader(line, *reader_args)
                        except:
                            raise OutputReadError("%s: couldn't read %s "
                                "with %s" % (self.id, filename, reader_name))
                        if not isinstance(data, dict):
                            raise OutputReadError("%s: %s for %s didn't "
                                                    "return a dict" \
                                        % (self.id, processor_type, filename))
                        for key, value in line_data.iteritems():
                            if key not in data:
                                data[key] = [value]
                            else:
                                data[key].append(value)
        if not data:
            raise OutputReadError("%s: no output processor defined for %s" \
                                % (self.id, filename))
        return data

    def plot_outputs(self):
        """Plots the experiment outputs according to the user specified
        plotting functions and output line parser
        
        Raises:
            OutputReaderror: if a output file couldn't be read
            PlotError: if plotting failed
        """
        plots = self._fields['plot']
        for plot_name in plots:
            #Construct the plotter and arguments
            self.plotter(plot_name)

    def plotter(self, plot_name, feedback=None):
        """Plots the outputfile into plot image using user defined plotting
        and output reading functions

        Parameters:
            plot_name (str): Name of the plot image
            feedback (obj): a feedback object fed into the plotting function

        Returns:
            feedback (obj): Object that can be fed back to the 
                            plotting function

        Raises:
            OutputReadError: When the output couldn't be read
            PlotError: When the plotting failed
        """
        if plot_name not in self.plot:
            raise PlotError("%s: no plot named %s defined" \
                                % (self.id, plot_name))
        #Get the output data as dict from the output file
        args = shlex.split(self.plot[plot_name])
        try:
            module_name = args[0]
            plotter_name = args[1]
            output_filename = args[2]
            plot_args = args[3:]
        except:
            raise PlotError("%s: couldn't parse plot arguments" % self.id)
        try:
            plotter = neronet.core.import_from(module_name, plotter_name)
        except:
            raise PlotError("%s: couldn't import %s from %s" \
                                % (self.id, plotter_name, module_name))
        #Reads the output file using user defined output reading function
        output = self.get_output(output_filename)

        #Convert plot argument key words to values
        plot_data = []
        for plot_arg in plot_args:
            if plot_arg in output:
                plot_arg = (plot_arg, output[plot_arg])
            plot_data.append(plot_arg)
        try:
            results_dir = self.get_results_dir()
            return plotter(os.path.join(results_dir, plot_name), \
                            feedback, *plot_data)
        except:
            raise PlotError("%s: couldn't plot %s, maybe something is wrong"
                            " with the plot function?" % (self.id, plot_name))

    def get_action(self, logrow):
        init_action = ('no action', '')
        try:
            for key in self._fields['conditions']:
                action = self._fields['conditions'][key].get_action(logrow)
                if action == 'kill':
                    return (action, key)
                elif action != 'no action':
                    init_action = (action, key)
        except TypeError:
            return init_action
        return init_action
       
    def set_warning(self, warning):
        """Called when a condition is met. Adds a warning message to self.warnings
           attributes:
               warning(str): the name/id of the condition that was met
        """
        self._fields['warnings'].append(str(datetime.datetime.now()) + ": The condition '" + warning + "' was met")
    
    def set_multiple_warnings(self, warnings):
        """Updates self.warnings to be exactly the same as the parameter given to
           this function.
           Parameters:
               warnings(list): List of warning messages
        """
        self._fields['warnings'] = warnings
            
    def has_warnings(self):
        if self._fields['warnings']:
            return 'WARNING'
        else:
            return ''
    
    def get_warnings(self):
        return self._fields['warnings']

    def __getattr__(self, attr):
        """Getter for the experiment class hides the inner dictionary"""
        #Gets the inner dictionary
        fields = super(Experiment, self).__getattribute__('_fields')
        if attr in fields:
            return fields[attr]
        #Gets hidden attributes by adding _
        if attr == 'id':
            attr = 'experiment_id'
        elif attr == 'state':
            return fields['states_info'][-1][0]
        elif attr == 'state_info':
            return fields['states_info'][-1]
        return super(Experiment, self).__getattribute__('_' + attr)

    def __setattr__(self, attr, value):
        """Setter for the experiment class
        
        Raises:
            AttributeError: if the attribute doesn't exist
        """
        #Gets the inner dictionary
        fields = super(Experiment, self).__getattribute__('_fields')
        if attr == 'id' or attr == 'experiment_id':
            super(Experiment, self).__setattr__('_experiment_id', value)
        elif attr in fields or attr in ('log_output', ):
            fields[attr] = value
        else:
            raise AttributeError('Experiment has no attribute named "%s"!' % attr)

    @property 
    def callstring(self):
        rcmd = self._fields['run_command_prefix']
        code_file = self._fields['main_code_file']
        parameters = self._fields['parameters']
        param_format = self._fields['parameters_format']
        parameters_string = param_format.format(**parameters)
        callstring = ' '.join([rcmd, code_file, parameters_string])
        return callstring

    def update_state(self, state):
        """ Updates the state
        """
        if state == self.state: return
        if state == 'running' and self._fields['conditions']:
            for c in self._fields['conditions']:
                self._fields['conditions'][c].start_time = datetime.datetime.now()
        self._fields['states_info'].append((state, datetime.datetime.now()))

        
    def as_gen(self):
        """Creates a generate that generates info about the experiment
        Yields:
            str: A line of experiment status
        """
        yield "%s\n" % self._experiment_id
        yield "  Run command: %s\n" % self._fields['run_command_prefix']
        yield "  Main code file: %s\n" % self._fields['main_code_file']
        params = self._fields['parameters_format'].format( \
            **self._fields['parameters'])
        yield "  Parameters: %s\n" % params
        yield "  Parameters format: %s\n" % self._fields['parameters_format']
        if self._fields['collection']:
            yield "  Collection: %s\n" % self._fields['collection']
        yield "  State: %s\n" % self.state
        if self._fields['cluster_id']:
            yield "  Cluster: " + self._fields['cluster_id'] + '\n'
        if self.state in (Experiment.State.running, Experiment.State.finished):
            can_process = False
            for output_file in self._fields['outputs']:
                if self._fields['output_line_processor']:
                    if output_file in self._fields['output_line_processor']:
                        can_process = True
                if self._fields['output_file_processor']:
                    if output_file in self._fields['output_file_processor']:
                        can_process = True
            if can_process:
                yield "  Output:\n"
                for output_file in self._fields['outputs']:
                    try:
                        output = self.get_output(output_file)
                        yield "    " + output_file + ":\n"
                        for field in output:
                            yield "      %s: " % field + str(output[field]) + "\n"
                    except OutputReadError as e:
                        pass
        yield "  Last modified: %s\n" % self._fields['time_modified']
        if self._fields['conditions']:            
            conds = '  Conditions:\n'
            for condition in self._fields['conditions']:
                conds +=  '    ' + self._fields['conditions'][condition].name + ':\n'
                conds +=  '      variablename: ' + self._fields['conditions'][condition].varname + '\n'
                conds +=  '      killvalue: ' + str(self._fields['conditions'][condition].killvalue) + '\n'
                conds +=  '      comparator: ' + self._fields['conditions'][condition].comparator + '\n'
                conds +=  '      when: ' + self._fields['conditions'][condition].when + '\n'
                conds +=  '      action: ' + self._fields['conditions'][condition].action + '\n'
            yield conds
        if self._fields['warnings']:
            warns = '  Warnings:\n'
            for warn in self._fields['warnings']:
                warns += '    ' + warn + '\n'
            yield warns

    def __str__(self):
        return "%s %s" % (self._experiment_id, self._fields['state'][-1][0])

def duplicate_experiment(experiment, experiment_id):
    definable_fields = MANDATORY_FIELDS | OPTIONAL_FIELDS
    experiment_data = {}
    for field in definable_fields:
        experiment_data[field] = experiment._fields[field]
    experiment_data['experiment_id'] = experiment_id
    experiment_data['path'] = experiment._fields['path']
    return Experiment(**experiment_data)

class ExperimentWarning:

    WARNING_FIELDS = set(['variablename', 'killvalue', 'comparator', 'when', \
                        'action'])

    def __init__(self, name, variablename, killvalue, comparator, when, action):
        self.name = name.strip()
        self.varname = variablename.strip()
        self.killvalue = killvalue
        self.comparator = comparator.strip()
        self.when = when.strip()
        self.action = action.strip()
        self.start_time = datetime.datetime.now()
            
    def get_action(self, logrow):
        logrow = logrow.strip()
        varlen = len(self.varname)
        check_condition = True
        if 'time' in self.when:
            time_when = float(self.when[4:].strip())
            time_passed = datetime.datetime.now() - self.start_time
            time_passed_sec = time_passed.days * 86400 + time_passed.seconds
            time_passed_min = time_passed_sec / 60
            if time_passed_min < time_when:
                check_condition = False
        if check_condition and logrow[:varlen].strip() == self.varname:
            varvalue = logrow[varlen:].strip()
            try:
                varvalue = float(varvalue)
            except:
                return 'no action'
            if any( [self.comparator == 'gt' and varvalue > self.killvalue,
                self.comparator == 'lt' and varvalue < self.killvalue,
                self.comparator == 'eq' and varvalue == self.killvalue,
                self.comparator == 'geq' and varvalue >= self.killvalue,
                self.comparator == 'leq' and varvalue <= self.killvalue] ):
                return self.action
        return 'no action'

    def __eq__(self, other):
        if not other:
            return False
        for value in ['name', 'varname', 'killvalue', 'comparator', 'when', 'action']:
            if getattr(self, value) != getattr(other, value): return False
        return True
