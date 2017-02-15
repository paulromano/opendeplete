""" Full system test suite. """

import shutil
import unittest

import numpy as np

import opendeplete
from opendeplete import results
from opendeplete import utilities
import test.example_geometry as example_geometry

class TestFull(unittest.TestCase):
    """ Full system test suite.

    Runs an entire OpenMC simulation with depletion coupling and verifies
    that the outputs match a reference file.  Sensitive to changes in
    OpenMC.
    """

    def test_full(self):
        """
        This test runs a complete OpenMC simulation and tests the outputs.
        It will take a while.
        """

        n_rings = 2
        n_wedges = 4

        # Load geometry from example
        geometry, volume, materials, lower_left, upper_right = \
            example_geometry.generate_problem(n_rings=n_rings, n_wedges=n_wedges)

        # Create dt vector for 3 steps with 15 day timesteps
        dt1 = 15*24*60*60  # 15 days
        dt2 = 1.5*30*24*60*60  # 1.5 months
        N = np.floor(dt2/dt1)

        dt = np.repeat([dt1], N)

        # Create settings variable
        settings = opendeplete.Settings()

        settings.chain_file = "chains/chain_simple.xml"
        settings.openmc_call = "openmc"
        settings.particles = 100
        settings.batches = 100
        settings.inactive = 40
        settings.lower_left = lower_left
        settings.upper_right = upper_right
        settings.entropy_dimension = [10, 10, 1]

        settings.round_number = True
        settings.constant_seed = 1

        settings.power = 2.337e15*4  # MeV/second cm from CASMO
        settings.dt_vec = dt
        settings.output_dir = "test_full"

        op = opendeplete.Operator()
        op.geometry_fill(geometry, volume, materials, settings)

        # Perform simulation using the predictor algorithm
        opendeplete.integrate(op, opendeplete.predictor_c0)

        # Load the files
        res_test = results.read_results(settings.output_dir + "/results")

        # Load the reference
        res_old = results.read_results("test/test_reference")

        # Assert same cells
        for cell in res_old[0].cell_to_ind:
            self.assertIn(cell, res_test[0].cell_to_ind,
                          msg="Cell " + cell + " not in new results.")
        for nuc in res_old[0].nuc_to_ind:
            self.assertIn(nuc, res_test[0].nuc_to_ind,
                          msg="Nuclide " + nuc + " not in new results.")

        for cell in res_test[0].cell_to_ind:
            self.assertIn(cell, res_old[0].cell_to_ind,
                          msg="Cell " + cell + " not in old results.")
        for nuc in res_test[0].nuc_to_ind:
            self.assertIn(nuc, res_old[0].nuc_to_ind,
                          msg="Nuclide " + nuc + " not in old results.")

        for cell in res_old[0].cell_to_ind:
            for nuc in res_old[0].nuc_to_ind:
                _, y_test = utilities.evaluate_single_nuclide(res_test, 0, cell,
                                                              nuc, use_interpolation=False)
                _, y_old = utilities.evaluate_single_nuclide(res_old, 0, cell,
                                                             nuc, use_interpolation=False)

                # Test each point

                tol = 1.0e-6

                correct = True
                for i in range(len(y_old)):
                    if y_old[i] != y_test[i]:
                        if y_old[i] != 0.0:
                            if np.abs(y_test[i] - y_old[i]) / y_old[i] > tol:
                                correct = False
                        else:
                            correct = False

                self.assertTrue(correct,
                                msg="Discrepancy in cell " + cell + " and nuc " + nuc
                                + "\n" + str(y_old) + "\n" + str(y_test))

    def tearDown(self):
        """ Clean up files"""
        shutil.rmtree("test_full", ignore_errors=True)


if __name__ == '__main__':
    unittest.main()