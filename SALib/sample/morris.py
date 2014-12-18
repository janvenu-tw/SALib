from __future__ import division
import numpy as np
import random as rd
from . import common_args
from . sample import Sample
from ..sample import morris_oat, morris_groups, morris_optimal
from ..util import read_param_file, read_group_file
from collections import Iterable, OrderedDict


def compute_groups_from_parameter_file(group_list, num_vars):
    '''
    Computes a k-by-g matrix which notes factor membership of groups
    where:
        k is the number of variables
        g is the number of groups
    Also returns a g-length list of unique group_names
    '''
    # Get a unique set of the group names
    unique_group_names = list(OrderedDict.fromkeys(group_list))
    number_of_groups = len(unique_group_names)

    indices = dict([(x,i) for (i,x) in enumerate(unique_group_names)])

    output = np.zeros((num_vars, number_of_groups), dtype=np.int)

    for parameter_row, group_membership in enumerate(group_list):
        group_index = indices[group_membership]
        output[parameter_row, group_index] = 1

    return np.matrix(output), unique_group_names


class Morris(Sample):
    '''
    A class which implements three variants of Morris' sampling for
    elementary effects:
            - vanilla Morris
            - optimised trajectories (Campolongo's enhancements from 2007)
            - groups with optimised trajectories (again Campolongo 2007)

    At present, optimised trajectories is implemented using a brute-force
    approach, which can be very slow, especially if you require more than four
    trajectories.  Note that the number of factors makes little difference,
    but the ratio between number of optimal trajectories and the sample size
    results in an exponentially increasing number of scores that must be
    computed to find the optimal combination of trajectories.

    I suggest going no higher than 4 from a pool of 100 samples.

    Suggested enhancements:
        - a parallel brute force method (incomplete)
        - a combinatorial optimisation approach (completed, but dependencies are
          not open-source)
    '''


    def __init__(self, parameter_file, samples, num_levels, grid_jump, \
                 group_file=None, optimal_trajectories=None):

        self.groups = None
        self.parameter_file = parameter_file
        self.samples = samples
        self.num_levels = num_levels
        self.grid_jump = grid_jump
        pf = read_param_file(self.parameter_file, True)
        self.num_vars = pf['num_vars']
        self.bounds = pf['bounds']
        self.parameter_names = pf['names']
        groups_from_parameter_file = pf['groups']
        if len(groups_from_parameter_file) > 0:
            self.groups, self.group_names = compute_groups_from_parameter_file(groups_from_parameter_file, self.num_vars)
            if np.all(self.groups == np.eye(self.num_vars)):
                self.groups = None
                self.group_names = None
        if group_file is not None:
            self.groups, self.group_names = self.compute_groups(group_file)
        self.optimal_trajectories = optimal_trajectories

        if self.optimal_trajectories != None:
            # Check to ensure that fewer optimal trajectories than samples are
            # requested, otherwise ignore
            if self.optimal_trajectories >= self.samples:
                raise ValueError("The number of optimal trajectories should be less than the number of samples.")
            elif self.optimal_trajectories > 10:
                raise ValueError("Running optimal trajectories greater than values of 10 will take a long time.")
            elif self.optimal_trajectories <= 1:
                raise ValueError("The number of optimal trajectories must be set to 2 or more.")

        if self.groups is None:

            self.create_sample()

        else:

            self.create_sample_with_groups()


    def flatten(self, l):
        for el in l:
            if isinstance(el, Iterable) and not isinstance(el, str):
                for sub in self.flatten(el):
                    yield sub
            else:
                yield el


    def compute_groups(self, group_file):
        gf = read_group_file(group_file)

        data = gf['groups']

        group_names = [g[0] for g in data]
        param_names_from_gf = [g[1] for g in data]
        param_names_to_check = [x for x in self.flatten(param_names_from_gf)]

        actual_names = self.parameter_names

        # Check parameter names in the group file match those from the parameter file
        if not all([x in actual_names for x in param_names_to_check]):
            print("Actual names: ", actual_names)
            print("Names from group file: ", [x for x in param_names_to_check])
            raise ValueError("The parameter names from the group file do not match those from the parameter file")

        # Compute the index of each parameter name and store in a dictionary
        indices = dict([(x,i) for (i,x) in enumerate(actual_names)])

        output = np.zeros((self.num_vars, len(group_names)))

        # Get the data from the group file...
        for row, group in enumerate(param_names_from_gf):
            for param in group:
                column = indices[param]
                output[column,row] = 1

        # ... and compile the numpy matrix
        return np.matrix(output, dtype=np.int), group_names


    def create_sample(self):

        if self.optimal_trajectories is None:

            optimal_sample = morris_oat.sample(self.samples,
                                               self.parameter_file,
                                               self.num_levels,
                                               self.grid_jump)

        else:

            sample = morris_oat.sample(self.samples,
                                       self.parameter_file,
                                       self.num_levels,
                                       self.grid_jump)
            optimal_sample = \
                morris_optimal.find_optimum_trajectories(sample,
                                                         self.samples,
                                                         self.num_vars,
                                                         self.optimal_trajectories)

        self.output_sample = optimal_sample


    def create_sample_with_groups(self):

        self.output_sample = morris_groups.sample(self.samples,
                                                  self.groups,
                                                  self.num_levels,
                                                  self.grid_jump)
        if self.optimal_trajectories is not None:
            self.output_sample = \
                morris_optimal.find_optimum_trajectories(self.output_sample,
                                                         self.samples,
                                                         self.num_vars,
                                                         self.optimal_trajectories)


    def debug(self):
        print("Parameter File: %s" % self.parameter_file)
        print("Number of samples: %s" % self.samples)
        print("Number of levels: %s" % self.num_levels)
        print("Grid step: %s" % self.grid_jump)
        print("Number of variables: %s" % self.num_vars)
        print("Parameter bounds: %s" % self.bounds)
        if self.groups is not None:
          print("Group: %s" % self.groups)
        if self.optimal_trajectories is not None:
          print("Number of req trajectories: %s" % self.optimal_trajectories)


if __name__ == "__main__":

    parser = common_args.create()
    parser.add_argument('-l','--levels', type=int, required=False,
                        default=4, help='Number of grid levels (Morris only)')
    parser.add_argument('--grid-jump', type=int, required=False,
                        default=2, help='Grid jump size (Morris only)')
    parser.add_argument('-k','--k-optimal', type=int, required=False,
                        default=None, help='Number of optimal trajectories (Morris only)')
    parser.add_argument('--group', type=str, required=False, default=None,
                       help='File path to grouping file (Morris only)')
    args = parser.parse_args()

    np.random.seed(args.seed)
    rd.seed(args.seed)

    sample = Morris(args.paramfile, args.samples, args.levels, \
                    args.grid_jump, args.group, args.k_optimal)

    sample.save_data(args.output, delimiter=args.delimiter, precision=args.precision)
