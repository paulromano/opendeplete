"""DepletionChain module.

This module contains information about a depletion chain.  A depletion chain is
loaded from an .xml file and all the nuclides are linked together.
"""

from collections import OrderedDict


class DepletionChain:
    def __init__(self):
        self.n_nuclides = None
        """int: Number of nuclides in chain."""
        self.n_fp_nuclides = None
        """int: Number of fission product nuclides in chain."""
        self.nuclides = None
        """list: List of Nuclide objects."""

        self.nuclide_dict = None
        """OrderedDict: Name to index in self.nuclides dictionary."""
        self.precursor_dict = None
        """OrderedDict: Name to index in precursor list."""

        self.yields = None
        """Yield: Yield object for fission."""

        self.reaction_list = None
        """list: List of reaction types."""

    def xml_read(self, filename):
        """ Reads a depletion chain xml file.

        Args:
            filename (str): The path to the depletion chain xml file.

        Todo:
            Allow for branching on capture, etc.
        """
        import xml.etree.ElementTree as ET
        import code
        import numpy as np
        import nuclide

        # Create variables
        self.n_nuclides = 0
        self.n_fp_nuclides = 0
        self.nuclides = []
        self.reaction_list = []
        self.nuclide_dict = OrderedDict()

        # Load XML tree
        root = ET.parse(filename)

        # Read nuclide tables
        decay_node = root.find('decay_constants')

        nuclide_index = 0

        for nuclide_node in decay_node.findall('nuclide_table'):
            self.n_nuclides += 1

            nuc = nuclide.Nuclide()

            # Just set it to zero to ensure it's set
            nuc.yield_ind = 0
            nuc.fission_power = 0.0

            nuc.name = nuclide_node.get('name')
            nuc.n_decay_paths = int(nuclide_node.get('decay_modes'))
            nuc.n_reaction_paths = int(nuclide_node.get('reactions'))

            self.nuclide_dict[nuc.name] = nuclide_index

            # Check for decay paths
            if nuc.n_decay_paths > 0:
                # Create objects
                nuc.decay_target = []
                nuc.decay_type = []
                nuc.branching_ratio = []

                nuc.half_life = float(nuclide_node.get('half_life'))

                for decay_node in nuclide_node.iter('decay_type'):
                    nuc.decay_target.append(decay_node.get('target'))
                    nuc.decay_type.append(decay_node.get('type'))
                    nuc.branching_ratio.append(float(decay_node.get('branching_ratio')))

            # Check for reaction paths
            if nuc.n_reaction_paths > 0:
                # Create objects
                nuc.reaction_target = []
                nuc.reaction_type = []

                for reaction_node in nuclide_node.iter('reaction_type'):
                    r_type = reaction_node.get('type')

                    # Add to total reaction types
                    if r_type not in self.reaction_list:
                        self.reaction_list.append(r_type)

                    nuc.reaction_type.append(r_type)
                    # If the type is not fission, get target, otherwise
                    # just set the variable to exists.
                    if r_type != 'fission':
                        nuc.reaction_target.append(reaction_node.get('target'))
                    else:
                        nuc.reaction_target.append(0)
                        nuc.fission_power = float(reaction_node.get('energy'))

            self.nuclides.append(nuc)
            nuclide_index += 1

        # Read neutron induced fission yields table
        nfy_node = root.find('neutron_fission_yields')

        self.yields = nuclide.Yield()

        # code.interact(local=locals())

        # Create and load all the variables
        self.yields.n_fis_prod = int(nfy_node.find('nuclides').text)
        self.yields.n_precursors = int(nfy_node.find('precursor').text)
        self.yields.n_energies = int(nfy_node.find('energy_points').text)

        temp = nfy_node.find('precursor_name').text
        self.yields.precursor_list = [x for x in temp.split()]

        temp = nfy_node.find('energy').text
        self.yields.energy_list = [float(x) for x in temp.split()]

        self.yields.energy_dict = OrderedDict()
        self.precursor_dict = OrderedDict()

        # Form dictionaries out of inverses of lists
        energy_index = 0

        for x in self.yields.energy_list:
            self.yields.energy_dict[x] = energy_index
            energy_index += 1

        precursor_index = 0

        for x in self.yields.precursor_list:
            self.precursor_dict[x] = precursor_index
            precursor_index += 1

        # Allocate variables
        self.yields.name = []

        self.yields.fis_yield_data = np.zeros([self.yields.n_fis_prod, self.yields.n_energies, self.yields.n_precursors])

        self.yields.fis_prod_dict = OrderedDict()

        product_index = 0

        # For eac fission product
        for yield_table_node in nfy_node.findall('nuclide_table'):
            name = yield_table_node.get('name')
            self.yields.name.append(name)

            nuc_ind = self.nuclide_dict[name]

            self.nuclides[nuc_ind].yield_ind = product_index

            # For each energy (table)
            for fy_table in yield_table_node.findall('fission_yields'):
                energy = float(fy_table.get('energy'))

                energy_index = self.yields.energy_dict[energy]

                self.yields.fis_prod_dict[name] = product_index
                temp = fy_table.find('fy_data').text
                self.yields.fis_yield_data[product_index, energy_index, :] = [float(x) for x in temp.split()]

            product_index += 1

    def form_matrix(self, rates):
        """ Forms depletion matrix.

        Args:
            rates (dict): Dictionary of dictionary of reaction rates by nuclide.
        """
        import scipy.sparse as sp
        import math

        matrix = sp.dok_matrix((self.n_nuclides, self.n_nuclides))

        for i in range(self.n_nuclides):
            nuclide = self.nuclides[i]

            if nuclide.n_decay_paths != 0:
                # Decay paths
                # Loss
                decay_constant = math.log(2)/nuclide.half_life

                matrix[i, i] -= decay_constant

                # Gain
                for j in range(nuclide.n_decay_paths):
                    target_nuclide = nuclide.decay_target[j]

                    # Allow for total annihilation for debug purposes
                    if target_nuclide != 'Nothing':
                        k = self.nuclide_dict[target_nuclide]

                        matrix[k, i] += nuclide.branching_ratio[j] * decay_constant

            for j in range(nuclide.n_reaction_paths):
                # Reaction paths
                n_rates = rates.rate[nuclide.name]
                # Loss
                matrix[i, i] -= n_rates[j]

                target_nuclide = nuclide.reaction_target[j]

                # TODO allow for branching ratio reactions.
                # For example, Am-241 (n,gamma) -> Am-242 or Am-242m
                # Or, to allow for alpha accumulation in fuel, etc.

                # Gain
                # Allow for total annihilation for debug purposes
                if target_nuclide != 'Nothing':
                    if nuclide.reaction_type[j] != 'fission':
                        k = self.nuclide_dict[target_nuclide]
                        matrix[k, i] += n_rates[j]
                    else:
                        m = self.precursor_dict[nuclide.name]

                        for k in range(self.yields.n_fis_prod):
                            l = self.nuclide_dict[self.yields.name[k]]
                            # Todo energy
                            matrix[l, i] += self.yields.fis_yield_data[k, 0, m] * n_rates[j]
        matrix = matrix.tocsr()
        return matrix

    def nuc_by_ind(self, ind):
        """ Extracts nuclides from the list by dictionary key.

        Args:
            ind (str): Name of nuclide.

        Returns:
            (Nuclide) Nuclide object with the name of ind.
        """
        return self.nuclides[self.nuclide_dict[ind]]


def matrix_wrapper(input_tuple):
    """ Parallel wrapper for matrix formation.

    This wrapper is used whenever a pmap/map-type function is used to make
    matrices for each cell in parallel.

    Args:
        input_tuple (tuple): Index 0 is the chain, index 1 is the reaction
                             rate array.

    Returns:
        (scipy.sparse.linalg.csr_matrix) The matrix for this reaction rate.
    """
    return input_tuple[0].form_matrix(input_tuple[1])
