import pint # For easy units
import subprocess
import numpy as np
import os
import shutil

# Get path to *this* file. Necessary when applying gmsh to the packaged geometry
full_path = os.path.realpath(__file__)
file_dir = os.path.dirname(full_path)
parent_dir = os.path.dirname(file_dir)

sim_setup_dir = file_dir + '/simulation_setups/yeast_radially_symmetric/'

# Define constants

ureg = pint.UnitRegistry()

D = 2.5e-6 * (ureg.cm**2 / ureg.sec)
r_petri = 8.7/2. * (ureg.cm) # cm
g = 9.80665 * (ureg.meter/ureg.second**2)  # meter/second^2

mu_dict = {}
mu_dict[2.2] = 30 * ureg.pascal * ureg.second
mu_dict[2.5] = 50 * ureg.pascal * ureg.second

rho_0 = 1.0167 * ureg.gram / ureg.milliliter
rho_f = 1.0077 * ureg.gram / ureg.milliliter

delta_rho = rho_0 - rho_f

beta = delta_rho /rho_f # Has units...but dimensionless when multiplied by c, which is what we use it for.

# The tricky parameter to fit: the mass flux per yeast cell! It should be on the
# order of, from my estimates, 2.5 pg/(um^2/hour). It *may* depend on if the yeast
# is covered or not with the fluid, so I'm going to keep it as an input parameter.
# The other parameters are relatively independent of exactly what we change.
# With that said, there are a couple of constants we can hand-wavily define for my use.

rho_yeast = 1.1029 * ureg.g/ureg.mL # From the yeast size measurement paper

r_single_yeast = 2.5 * ureg.um # From the yeast size measurement paper

t_yeast = 90*ureg.minute # Yeast generation time estimation while fermenting

A_single_yeast_projection = (np.pi*r_single_yeast**2).to(ureg.um**2)

V_single_yeast = ((4./3.)*np.pi*r_single_yeast**3).to(ureg.um**3)

m_single_yeast = (rho_yeast * V_single_yeast).to(ureg.pg)

# Therefore, our best estimate of the mass flux is...
j_m_single_yeast = (m_single_yeast / (A_single_yeast_projection * t_yeast)).to(ureg.pg/(ureg.hour * ureg.um**2))

class Simulation(object):
    def __init__(self, V=None, mu=None, r_yeast=None, j_m_colony=None, sim_path=None):
        self.V = V  # Volume: must have units
        self.mu = mu # Viscosity: must have units
        self.r_yeast = r_yeast # Physical radius of yeast colony
        self.j_m_colony = j_m_colony # Mass flux per unit area of yeast
        self.sim_path = sim_path

        self.nu = (self.mu / rho_0)
        self.nu.ito(ureg.centimeter ** 2 / ureg.second)

        self.h = self.V / (np.pi * r_petri ** 2)
        self.h.ito(ureg.mm)

        # Calculate Ra_star
        self.Ra_star = (self.h ** 3) * g * beta / (D * self.nu)
        self.Ra_star.ito_base_units()

        # Set the characteristic length and time scale
        self.Lc = self.h
        self.Tc = (self.h ** 2 / D).to(ureg.day)

        # Calculate the dimensionless length of the yeast
        self.nd_r_yeast = (self.r_yeast / self.Lc).to_base_units()

        # Calculate the dimensionless length of the petri dish
        self.nd_r_petri = (r_petri / self.Lc).to_base_units()

        # Get G based on the input parameters
        self.G = (self.h*self.j_m_colony)/(D*rho_0*beta)
        self.G.ito(ureg.dimensionless)

    def create_gmsh(self, mesh_name, mesh_size=0.1, slice_angle=2.5):
        lc = mesh_size
        r_yeast = self.nd_r_yeast.magnitude
        r_petri = self.nd_r_petri.magnitude

        subprocess.call(['gmsh', '-1', '-2', '-3',
                         '-setnumber', 'lc', str(lc),
                         '-setnumber', 'r_yeast', str(r_yeast),
                         '-setnumber', 'r_petri', str(r_petri),
                         '-setnumber', 'slice_angle', str(slice_angle),
                         sim_setup_dir + '/yeast_radially_symmetric.geo',
                         '-o', self.sim_path + str(mesh_name)]
                        )

    def create_openfoam_sim(self):
        # Copy the skeleton into the new location. If the location already exists, delete & replace.
        if os.path.isdir(self.sim_path):
            shutil.rmtree(self.sim_path)
        shutil.copytree(sim_setup_dir, self.sim_path)