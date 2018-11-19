from ase import Atom, Atoms
from math import floor
import numpy as np
import os

__author__ = "Alexander Gabourie"
__email__ = "gabourie@stanford.edu"


#########################################
# Structure preprocessing
#########################################

def __get_group(split, pos, direction):
    '''
    Gets the group that an atom belongs to based on its position. Only works in
    one direction as it is used for NEMD.

    Args:
        split (list(float)):
            List of boundaries. First element should be lower boundary of
            sim. box in specified direction and the last the upper.

        position (float):
            Position of the atom

        direction (str):
            Which direction the split will work

    Returns:
        out (int):
            Group of atom

    '''
    if direction == 'x':
        d = pos[0]
    elif direction == 'y':
        d = pos[1]
    else:
        d = pos[2]
    errmsg = 'Out of bounds error: {}'.format(d)
    for i,val in enumerate(split[:-1]):
        if i == 0 and d < val:
            print errmsg
            return -1
        if d >= val and d < split[i+1]:
            return i
    print errmsg
    return -1

def assign_groups(split, atoms, direction):
    '''
    Assigns groups to all atoms based on its position. Only works in
    one direction as it is used for NEMD. ASE Atom tag is used as group ID.
    Returns a bookkeeping parameter, but atoms will be udated in place.

    Args:
        split (list(float)):
            List of boundaries. First element should be lower boundary of sim.
            box in specified direction and the last the upper.

        atoms (ase.Atoms):
            Atoms to group

        direction (str):
            Which direction the split will work

    Returns:
        counts (int)
            A list of number of atoms in each group

    '''
    counts = [0]*(len(split)-1)
    for atom in atoms:
        i = __get_group(split, atom.position, direction)
        atom.tag = i
        counts[i] += 1
    return counts
