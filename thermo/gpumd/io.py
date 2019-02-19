from ase.io import write
from ase.io import read
from ase import Atom, Atoms
from math import floor
import numpy as np

__author__ = "Alexander Gabourie"
__email__ = "gabourie@stanford.edu"

#########################################
# Helper Functions
#########################################

def __get_atom_line(atom, velocity, layer, groups, type_dict, info):
    '''
    Constructs an atom's line in an xyz.in file.

    Args:
        atom (ase.Atom):
            Atom object to write to file.

        velocity (bool):
            If velocities need to be added.

        layer (bool):
            If the layer number needs to be added.

        groups (bool):
            If the groups need to be added.

        type_dict (dict):
            Dictionary to convert symbol to type number.

        info (dict):
            Dictionary that stores all velocity, layer, and groups data.

    Returns:
        out (str)
            The line to be printed to file.
    '''
    option = info[atom.index]
    required = ' '.join([str(type_dict[atom.symbol])] + \
                    [str(val) for val in list(atom.position)] + \
                    [str(atom.mass)])
    optional = ''
    if velocity:
        optional += ' ' + ' '.join([str(val) for val in option['velocity']])
    if layer:
        optional += ' ' + str(option['layer'])
    if groups:
        optional += ' ' + ' '.join([str(val) for val in option['groups']])
    return required + optional

def __set_atoms(atoms, types):
    """
    Sets the atom symbols for atoms loaded from GPUMD where in.xyz does not
    contain that information

    Args:
        atoms (ase.Atoms):
            Atoms object to change symbols in

        types (list(str)):
            List of strings to assign to atomic symbols

    """
    for atom in atoms:
        atom.symbol = types[atom.number]

def __atom_type_sortkey(atom, atom_order=None):
    """
    Used as a key for sorting atom type for GPUMD in.xyz files

    Args:
        atom (ase.Atom):
            Atom object

        atom_order (list(str)):
            A list of atomic symbol strings in the desired order.

    """
    if atom_order:
        for i, sym in enumerate(atom_order):
            if sym == atom.symbol:
                return i
    else:
        ValueError('type sortkey error: Missing atom_order.')
        return 0

def __atom_group_sortkey(atom, info=None, group_index=None):
    """
    Used as a key for sorting atom groups for GPUMD in.xyz files

    Args:
        atom (ase.Atom):
            Atom object

        info (dict):
            Info dictionary for Atoms object that 'atom' belongs to. Stores velocity,
            groups, & layer information

        group_index (int):
            Index of the grouping list that is part of the 'groups' key for the atom.index
            element from the info dictionary.

    """
    if info and not group_index is None:
        return info[atom.index]['groups'][group_index]
    else:
        ValueError('group sortkey error: Missing either info or group_index.')
        return 0

def __atom_layer_sortkey(atom, info=None):
    """
    Used as a key for sorting atom layers for GPUMD in.xyz files

    Args:
        atom (ase.Atom):
            Atom object

        info (dict):
            Info dictionary for Atoms object that 'atom' belongs to. Stores velocity,
            groups, & layer information

    """
    if info:
        return info[atom.index]['layer']
    else:
        ValueError('layer sortkey error: Missing info.')
        return 0

#########################################
# Read Related
#########################################

def load_xyz(filename='xyz.in', atom_types=None):
    """
    Reads and returns the structure input file from GPUMD.

    Args:
        filename (str):
            Name of structure file

        atom_types (list(str)):
            List of atom types (elements).

    Returns:
        atoms (ase.Atoms):
            ASE atoms object with x,y,z, mass, group, type, cell, and PBCs
            from input file. group is stored in tag, atom type may not
            correspond to correct atomic symbol
        M (int):
            Max number of neighbor atoms

        cutoff (float):
            Initial cutoff for neighbor list build
    """
    # read file
    with open(filename) as f:
        xyz_lines = f.readlines()

    # get global structure params
    l1 = tuple(xyz_lines[0].split()) # first line
    N, M, use_triclinic, has_velocity, \
        has_layer, num_of_groups = [int(val) for val in l1[:2]+l1[3:]]
    cutoff = float(l1[2])
    l2 = tuple(xyz_lines[1].split()) # second line
    if use_triclinic:
        pbc, cell = [int(val) for val in l2[:3]], [float(val) for val in l2[3:]]
    else:
        pbc, L = [int(val) for val in l2[:3]], [float(val) for val in l2[3:]]

    # get atomic params
    info = dict()
    atoms = Atoms()
    atoms.set_pbc((pbc[0], pbc[1], pbc[2]))
    if use_triclinic:
        atoms.set_cell(np.array(cell).reshape((3,3)))
    else:
        atoms.set_cell([(L[0], 0, 0), (0, L[1], 0), (0, 0, L[2])])

    for index, line in enumerate(xyz_lines[2:]):
        data = dict()
        lc = tuple(line.split()) # current line
        type_, mass = int(lc[0]), float(lc[4])
        position = [float(val) for val in lc[1:4]]
        atom = Atom(type_, position, mass=mass)
        lc = lc[5:] # reduce list length for easier indexing
        if has_velocity:
            velocity = [float(val) for val in lc[:3]]
            lc = lc[3:]
            data['velocity'] = velocity
        if has_layer:
            layer = int(lc[0])
            lc = lc[1:]
            data['layer'] = layer
        if num_of_groups:
            groups = [int(group) for group in lc]
            data['groups'] = groups
        atoms.append(atom)
        info[index] = data

    atoms.info = info
    if atom_types:
        __set_atoms(atoms, atom_types)

    return atoms, M, cutoff

def load_traj(traj_file='xyz.out', in_file='xyz.in', atom_types=None):
    """
    Reads the trajectory from GPUMD run and creates a list of ASE atoms.

    Args:
        traj_file (str):
            Name of the file that hold the GPUMD trajectory

        in_file (str):
            Name of the original structure input file. Needed to get atom
            type, mass, etc

        atom_types (list(str)):
            List of atom types (elements).

    Returns:
        traj (list(ase.Atoms)):
            A list of ASE atoms objects.
    """
    # read trajectory file
    with open(traj_file, 'r') as f:
        xyz_lines = f.readlines()

    atoms_in, M, cutoff = load_xyz(in_file, atom_types)
    N = len(atoms_in)

    num_frames = len(xyz_lines)/float(N)
    if not (num_frames == floor(num_frames)):
        print('load_traj warning: Non-integer number of frames base on number of atoms.' +
              ' Only taking {} frames'.format(floor(num_frames)))

    num_frames = int(floor(num_frames))
    traj = list()
    for frame in range(num_frames):
        for i, line in enumerate(xyz_lines[frame*N:(frame+1)*N]):
            curr_atom = atoms_in[i]
            curr_atom.position = tuple([float(val) for val in line.split()])
        traj.append(atoms_in.copy())

    return traj

#########################################
# Write Related
#########################################

def convert_gpumd_atoms(in_file='xyz.in', out_filename='in.xyz',
                            format='xyz', atom_types=None):
    """
    Converts the GPUMD input structure file to any compatible ASE
    output structure file.
    Warning: Info dictionary may not be preserved.

    Args:
        in_file (str):
            GPUMD position file to get structure from

        out_filename (str):
            Name of output file after conversion

        format (str):
            ASE supported output format

        atom_types (list(str)):
            List of atom types (elements).

    """
    atoms, M, cutoff = load_xyz(in_file, atom_types)
    write(out_filename, atoms, format)
    return

def convert_gpumd_traj(traj_file='xyz.out', out_filename='out.xyz',
                       in_file='xyz.in', format='xyz'):
    """
    Converts GPUMD trajectory to any compatible ASE output. Default: xyz

    Args:
        traj_file (str):
            Trajetory from GPUMD

        out_filename (str):
            File in which final trajectory should be saved

        in_file (str):
            Original stucture input file to GPUMD. Needed to get atom
            numbers/types

        format (str):
            ASE supported format

    """
    traj = load_traj(traj_file, in_file)
    write(out_filename, traj, format)
    return

def lammps_atoms_to_gpumd(filename, M, cutoff, style='atomic',
                        gpumd_file='xyz.in'):
    """
    Converts a lammps data file to GPUMD compatible position file

    Args:
        filename (str):
            LAMMPS data file name

        M (int):
            Maximum number of neighbors for one atom

        cutoff (float):
            Initial cutoff distance for building the neighbor list

        style (str):
            Atom style used in LAMMPS data file

        gpumd_file (str):
            File to save the structure data to

    """
    # Load atoms
    atoms = read(filename, format='lammps-data', style=style)
    ase_atoms_to_gpumd(atoms, M, cutoff, gpumd_file=gpumd_file)
    return


def ase_atoms_to_gpumd(atoms, M, cutoff, gpumd_file='xyz.in', sort_key=None,
        atom_order=None):
    """
    Converts ASE atoms to GPUMD compatible position file

    Args:
        atoms (ase.Atoms):
            Atoms to write to gpumd file

        M (int):
            Maximum number of neighbors for one atom

        cutoff (float):
            Initial cutoff distance for building the neighbor list

        gpumd_file (str):
            File to save the structure data to

        sort_key (str):
            How to sort atoms ('group', 'type'). Default is None.

        atom_order (list(str)):
            List of atomic symbols in order to be listed in GPUMD xyz file.
            Default is None

    """

    if sort_key == 'type':
        atoms_list = sorted(atoms, key=lambda x: __atoms_sortkey(x, atom_order))
    elif sort_key == 'group':
        atoms_list = sorted(atoms, key=lambda x: __atoms_sortkey(x))
    else:
        atoms_list = atoms

    if sort_key=='type' and atom_order:
        types = atom_order
    else:
        types = list(set(atoms.get_chemical_symbols()))

    type_dict = dict()
    for i, type_ in enumerate(types):
        type_dict[type_] = i

    N = len(atoms)
    pbc = [str(1) if val else str(0) for val in atoms.get_pbc()]
    lx, ly, lz, a1, a2, a3 = tuple(atoms.get_cell_lengths_and_angles())
    lx, ly, lz = str(lx), str(ly), str(lz)
    if not (a1 == a2 == a3):
        raise ValueError('Structure must be orthorhombic.')

    with open(gpumd_file, 'w') as f:
        f.writelines(' '.join([str(N), str(M), str(cutoff)]) + '\n')
        f.writelines(' '.join(pbc + [lx, ly, lz]) + '\n')
        for atom in atoms_list[:-1]:
            type_ = [type_dict[atom.symbol], atom.tag, atom.mass] + list(atom.position)
            f.writelines(' '.join([str(val) for val in type_]) + '\n')
        # Last line
        atom = atoms_list[-1]
        type_ = [type_dict[atom.symbol], atom.tag, atom.mass] + list(atom.position)
        f.writelines(' '.join([str(val) for val in type_]))
    return
