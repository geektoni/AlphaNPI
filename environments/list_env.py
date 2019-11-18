import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from collections import OrderedDict
from environments.environment import Environment


class ListEnvEncoder(nn.Module):
    '''
    Implement an encoder (f_enc) specific to the List environment. It encodes observations e_t into
    vectors s_t of size D = encoding_dim.
    '''

    def __init__(self, observation_dim, encoding_dim):
        super(ListEnvEncoder, self).__init__()
        self.l1 = nn.Linear(observation_dim, 100)
        self.l2 = nn.Linear(100, encoding_dim)

    def forward(self, x):
        x = F.relu(self.l1(x))
        x = torch.tanh(self.l2(x))
        return x


class ListEnv(Environment):
    """Class that represents a list environment. It represents a list of size length of digits. The digits are 10-hot-encoded.
    There are two pointers, each one pointing on a list element. Both pointers can point on the same element.

    The environment state is composed of a scratchpad of size length x 10 which contains the list elements encodings
    and of the two pointers positions.

    An observation is composed of the two encoding of the elements at both pointers positions.

    Primary actions may be called to move pointers and swap elements at their positions.

    We call episode the sequence of actions applied to the environment and their corresponding states.
    The episode stops when the list is sorted.
    """

    def __init__(self, length=10, encoding_dim=32, hierarchy=True):

        assert length > 0, "length must be a positive integer"
        self.length = length
        self.scratchpad_ints = np.zeros((length,))
        self.p1_pos = 0
        self.p2_pos = 0
        self.encoding_dim = encoding_dim
        self.has_been_reset = False

        if hierarchy:
            self.programs_library = {'PTR_1_LEFT': {'level': 0, 'recursive': False},
                                     'STOP': {'level': -1, 'recursive': False},
                                     'PTR_2_LEFT': {'level': 0, 'recursive': False},
                                     'PTR_1_RIGHT': {'level': 0, 'recursive': False},
                                     'PTR_2_RIGHT': {'level': 0, 'recursive': False},
                                     'SWAP': {'level': 0, 'recursive': False},
                                     'RSHIFT': {'level': 1, 'recursive': False},
                                     'LSHIFT': {'level': 1, 'recursive': False},
                                     'COMPSWAP': {'level': 1, 'recursive': False},
                                     'RESET': {'level': 2, 'recursive': False},
                                     'BUBBLE': {'level': 2, 'recursive': False},
                                     'BUBBLESORT': {'level': 3, 'recursive': False}}
            for idx, key in enumerate(sorted(list(self.programs_library.keys()))):
                self.programs_library[key]['index'] = idx

            self.prog_to_func = {'STOP': self._stop,
                                 'PTR_1_LEFT': self._ptr_1_left,
                                 'PTR_2_LEFT': self._ptr_2_left,
                                 'PTR_1_RIGHT': self._ptr_1_right,
                                 'PTR_2_RIGHT': self._ptr_2_right,
                                 'SWAP': self._swap}

            self.prog_to_precondition = {'STOP': self._stop_precondition,
                                         'RSHIFT': self._rshift_precondition,
                                         'LSHIFT': self._lshift_precondition,
                                         'COMPSWAP': self._compswap_precondition,
                                         'RESET': self._reset_precondition,
                                         'BUBBLE': self._bubble_precondition,
                                         'BUBBLESORT': self._bubblesort_precondition,
                                         'PTR_1_LEFT': self._ptr_1_left_precondition,
                                         'PTR_2_LEFT': self._ptr_2_left_precondition,
                                         'PTR_1_RIGHT': self._ptr_1_right_precondition,
                                         'PTR_2_RIGHT': self._ptr_2_right_precondition,
                                         'SWAP': self._swap_precondition}

            self.prog_to_postcondition = {'RSHIFT': self._rshift_postcondition,
                                          'LSHIFT': self._lshift_postcondition,
                                          'COMPSWAP': self._compswap_postcondition,
                                          'RESET': self._reset_postcondition,
                                          'BUBBLE': self._bubble_postcondition,
                                          'BUBBLESORT': self._bubblesort_postcondition}

        else:
            # In no hierarchy mode, the only non-zero program is Bubblesort

            self.programs_library = {'PTR_1_LEFT': {'level': 0, 'recursive': False},
                                     'STOP': {'level': -1, 'recursive': False},
                                     'PTR_2_LEFT': {'level': 0, 'recursive': False},
                                     'PTR_1_RIGHT': {'level': 0, 'recursive': False},
                                     'PTR_2_RIGHT': {'level': 0, 'recursive': False},
                                     'SWAP': {'level': 0, 'recursive': False},
                                     'BUBBLESORT': {'level': 1, 'recursive': False}}
            for idx, key in enumerate(sorted(list(self.programs_library.keys()))):
                self.programs_library[key]['index'] = idx

            self.prog_to_func = {'STOP': self._stop,
                                 'PTR_1_LEFT': self._ptr_1_left,
                                 'PTR_2_LEFT': self._ptr_2_left,
                                 'PTR_1_RIGHT': self._ptr_1_right,
                                 'PTR_2_RIGHT': self._ptr_2_right,
                                 'SWAP': self._swap}

            self.prog_to_precondition = {'STOP': self._stop_precondition,
                                         'BUBBLESORT': self._bubblesort_precondition,
                                         'PTR_1_LEFT': self._ptr_1_left_precondition,
                                         'PTR_2_LEFT': self._ptr_2_left_precondition,
                                         'PTR_1_RIGHT': self._ptr_1_right_precondition,
                                         'PTR_2_RIGHT': self._ptr_2_right_precondition,
                                         'SWAP': self._swap_precondition}

            self.prog_to_postcondition = {'BUBBLESORT': self._bubblesort_postcondition}

        super(ListEnv, self).__init__(self.programs_library, self.prog_to_func,
                                               self.prog_to_precondition, self.prog_to_postcondition)

    def _ptr_1_left(self):
        """Move pointer 1 to the left."""
        if self.p1_pos > 0:
            self.p1_pos -= 1

    def _ptr_1_left_precondition(self):
        return self.p1_pos > 0

    def _stop(self):
        """Do nothing. The stop action does not modify the environment."""
        pass

    def _stop_precondition(self):
        return True

    def _ptr_2_left(self):
        """Move pointer 2 to the left."""
        if self.p2_pos > 0:
            self.p2_pos -= 1

    def _ptr_2_left_precondition(self):
        return self.p2_pos > 0

    def _ptr_1_right(self):
        """Move pointer 1 to the right."""
        if self.p1_pos < (self.length - 1):
            self.p1_pos += 1

    def _ptr_1_right_precondition(self):
        return self.p1_pos < self.length-1

    def _ptr_2_right(self):
        """Move pointer 2 to the right."""
        if self.p2_pos < (self.length - 1):
            self.p2_pos += 1

    def _ptr_2_right_precondition(self):
        return self.p2_pos < self.length-1

    def _swap(self):
        """Swap the elements pointed by pointers 1 and 2."""
        self.scratchpad_ints[[self.p1_pos, self.p2_pos]] = self.scratchpad_ints[[self.p2_pos, self.p1_pos]]

    def _swap_precondition(self):
        return self.p1_pos != self.p2_pos

    def _compswap_precondition(self):
        bool = self.p1_pos < self.length-1
        bool &= self.p2_pos == self.p1_pos or self.p2_pos == (self.p1_pos + 1)
        return bool

    def _lshift_precondition(self):
        return self.p1_pos > 0 or self.p2_pos > 0

    def _rshift_precondition(self):
        return self.p1_pos < self.length-1 or self.p2_pos < self.length-1

    def _bubble_precondition(self):
        bool = self.p1_pos == 0
        bool &= ((self.p2_pos == 0) or (self.p2_pos == 1))
        return bool

    def _reset_precondition(self):
        bool = True
        return bool

    def _bubblesort_precondition(self):
        bool = self.p1_pos == 0
        bool &= self.p2_pos == 0
        return bool

    def _compswap_postcondition(self, init_state, state):
        new_scratchpad_ints, new_p1_pos, new_p2_pos = init_state
        new_scratchpad_ints = np.copy(new_scratchpad_ints)
        if new_p1_pos == new_p2_pos and new_p2_pos < self.length-1:
            new_p2_pos += 1
        idx_left = min(new_p1_pos, new_p2_pos)
        idx_right = max(new_p1_pos, new_p2_pos)
        if new_scratchpad_ints[idx_left] > new_scratchpad_ints[idx_right]:
            new_scratchpad_ints[[idx_left, idx_right]] = new_scratchpad_ints[[idx_right, idx_left]]
        new_state = (new_scratchpad_ints, new_p1_pos, new_p2_pos)
        return self.compare_state(state, new_state)

    def _lshift_postcondition(self, init_state, state):
        init_scratchpad_ints, init_p1_pos, init_p2_pos = init_state
        scratchpad_ints, p1_pos, p2_pos = state
        bool = np.array_equal(init_scratchpad_ints, scratchpad_ints)
        if init_p1_pos > 0:
            bool &= p1_pos == (init_p1_pos-1)
        else:
            bool &= p1_pos == init_p1_pos
        if init_p2_pos > 0:
            bool &= p2_pos == (init_p2_pos-1)
        else:
            bool &= p2_pos == init_p2_pos
        return bool

    def _rshift_postcondition(self, init_state, state):
        init_scratchpad_ints, init_p1_pos, init_p2_pos = init_state
        scratchpad_ints, p1_pos, p2_pos = state
        bool = np.array_equal(init_scratchpad_ints, scratchpad_ints)
        if init_p1_pos < self.length-1:
            bool &= p1_pos == (init_p1_pos+1)
        else:
            bool &= p1_pos == init_p1_pos
        if init_p2_pos < self.length-1:
            bool &= p2_pos == (init_p2_pos+1)
        else:
            bool &= p2_pos == init_p2_pos
        return bool

    def _reset_postcondition(self, init_state, state):
        init_scratchpad_ints, init_p1_pos, init_p2_pos = init_state
        scratchpad_ints, p1_pos, p2_pos = state
        bool = np.array_equal(init_scratchpad_ints, scratchpad_ints)
        bool &= (p1_pos == 0 and p2_pos == 0)
        return bool

    def _bubblesort_postcondition(self, init_state, state):
        scratchpad_ints, p1_pos, p2_pos = state
        # check if list is sorted
        return np.all(scratchpad_ints[:self.length-1] <= scratchpad_ints[1:self.length])

    def _bubble_postcondition(self, init_state, state):
        new_scratchpad_ints, new_p1_pos, new_p2_pos = init_state
        new_scratchpad_ints = np.copy(new_scratchpad_ints)
        for idx in range(0, self.length-1):
            if new_scratchpad_ints[idx+1] < new_scratchpad_ints[idx]:
                new_scratchpad_ints[[idx, idx+1]] = new_scratchpad_ints[[idx+1, idx]]
        # bubble is expected to terminate with both pointers at the extreme left of the list
        new_p1_pos = self.length-1
        new_p2_pos = self.length-1
        new_state = (new_scratchpad_ints, new_p1_pos, new_p2_pos)
        return self.compare_state(state, new_state)

    def _one_hot_encode(self, digit, basis=10):
        """One hot encode a digit with basis.

        Args:
          digit: a digit (integer between 0 and 9)
          basis:  (Default value = 10)

        Returns:
          a numpy array representing the 10-hot-encoding of the digit

        """
        encoding = np.zeros(basis)
        encoding[digit] = 1
        return encoding

    def _one_hot_decode(self, one_encoding):
        """Returns digit associated to a one hot encoding.

        Args:
          one_encoding: numpy array representing the 10-hot-encoding of a digit.

        Returns:
          the digit encoded in one_encoding

        """
        return np.argmax(one_encoding)

    def reset_env(self):
        """Reset the environment. The list are values are draw randomly. The pointers are initialized at position 0
        (at left position of the list).

        """
        self.scratchpad_ints = np.random.randint(10, size=self.length)
        current_task_name = self.get_program_from_index(self.current_task_index)
        if current_task_name == 'BUBBLE' or current_task_name == 'BUBBLESORT':
            init_pointers_pos1 = 0
            init_pointers_pos2 = 0
        elif current_task_name == 'RESET':
            while True:
                init_pointers_pos1 = int(np.random.randint(0, self.length))
                init_pointers_pos2 = int(np.random.randint(0, self.length))
                if not (init_pointers_pos1 == 0 and init_pointers_pos2 == 0):
                    break
        elif current_task_name == 'LSHIFT':
            while True:
                init_pointers_pos1 = int(np.random.randint(0, self.length))
                init_pointers_pos2 = int(np.random.randint(0, self.length))
                if not (init_pointers_pos1 == 0 and init_pointers_pos2 == 0):
                    break
        elif current_task_name == 'RSHIFT':
            while True:
                init_pointers_pos1 = int(np.random.randint(0, self.length))
                init_pointers_pos2 = int(np.random.randint(0, self.length))
                if not (init_pointers_pos1 == self.length - 1 and init_pointers_pos2 == self.length - 1):
                    break
        elif current_task_name == 'COMPSWAP':
            init_pointers_pos1 = int(np.random.randint(0, self.length - 1))
            init_pointers_pos2 = int(np.random.choice([init_pointers_pos1, init_pointers_pos1 + 1]))
        else:
            raise NotImplementedError('Unable to reset env for this program...')

        self.p1_pos = init_pointers_pos1
        self.p2_pos = init_pointers_pos2
        self.has_been_reset = True

    def get_state(self):
        """Returns the current state.

        Returns:
            the environment state

        """
        assert self.has_been_reset, 'Need to reset the environment before getting states'
        return np.copy(self.scratchpad_ints), self.p1_pos, self.p2_pos

    def get_observation(self):
        """Returns an observation of the current state.

        Returns:
            an observation of the current state
        """
        assert self.has_been_reset, 'Need to reset the environment before getting observations'

        p1_val = self.scratchpad_ints[self.p1_pos]
        p2_val = self.scratchpad_ints[self.p2_pos]
        is_sorted = int(self._is_sorted())
        pointers_same_pos = int(self.p1_pos == self.p2_pos)
        pt_1_left = int(self.p1_pos == 0)
        pt_2_left = int(self.p2_pos == 0)
        pt_1_right = int(self.p1_pos == (self.length - 1))
        pt_2_right = int(self.p2_pos == (self.length - 1))
        p1p2 = np.eye(10)[[p1_val, p2_val]].reshape(-1)
        bools = np.array([
            pt_1_left,
            pt_1_right,
            pt_2_left,
            pt_2_right,
            pointers_same_pos,
            is_sorted
        ])
        return np.concatenate((p1p2, bools), axis=0)

    def get_observation_dim(self):
        """

        Returns:
            the size of the observation tensor
        """
        return 2 * 10 + 6

    def reset_to_state(self, state):
        """

        Args:
          state: a given state of the environment
        reset the environment is the given state

        """
        self.scratchpad_ints = state[0].copy()
        self.p1_pos = state[1]
        self.p2_pos = state[2]

    def _is_sorted(self):
        """Assert is the list is sorted or not.

        Args:

        Returns:
            True if the list is sorted, False otherwise

        """
        arr = self.scratchpad_ints
        return np.all(arr[:-1] <= arr[1:])

    def get_state_str(self, state):
        """Print a graphical representation of the environment state"""
        scratchpad = state[0].copy()  # check
        p1_pos = state[1]
        p2_pos = state[2]
        str = 'list: {}, p1 : {}, p2 : {}'.format(scratchpad, p1_pos, p2_pos)
        return str

    def compare_state(self, state1, state2):
        """
        Compares two states.

        Args:
            state1: a state
            state2: a state

        Returns:
            True if both states are equals, False otherwise.

        """
        bool = True
        bool &= np.array_equal(state1[0], state2[0])
        bool &= (state1[1] == state2[1])
        bool &= (state1[2] == state2[2])
        return bool

class QuickSortListEnv(Environment):
    """Class that represents a list environment. It represents a list of size length of digits. The digits are 10-hot-encoded.
    There are two pointers, each one pointing on a list element. Both pointers can point on the same element.

    The environment state is composed of a scratchpad of size length x 10 which contains the list elements encodings
    and of the two pointers positions.

    An observation is composed of the two encoding of the elements at both pointers positions.

    Primary actions may be called to move pointers and swap elements at their positions.

    We call episode the sequence of actions applied to the environment and their corresponding states.
    The episode stops when the list is sorted.
    """

    def __init__(self, length=10, encoding_dim=32, hierarchy=True):

        assert length > 0, "length must be a positive integer"
        self.length = length
        self.scratchpad_ints = np.zeros((length,))
        self.p1_pos = 0
        self.p2_pos = 0
        self.p3_pos = 0
        self.prog_stack = []
        self.encoding_dim = encoding_dim
        self.has_been_reset = False

        if hierarchy:
            self.programs_library = OrderedDict(sorted({'PTR_1_LEFT': {'level': 0, 'recursive': False},
                                     'STOP': {'level': -1, 'recursive': False},
                                     'PTR_2_LEFT': {'level': 0, 'recursive': False},
                                     'PTR_1_RIGHT': {'level': 0, 'recursive': False},
                                     'PTR_2_RIGHT': {'level': 0, 'recursive': False},
                                     'PTR_3_LEFT': {'level': 0, 'recursive': False},
                                     'PTR_3_RIGHT': {'level': 0, 'recursive': False},
                                     'SWAP': {'level': 0, 'recursive': False},
                                     'SWAP_2': {'level': 0, 'recursive': False},
                                     'SWAP_3': {'level': 0, 'recursive': False},
                                     'PUSH': {'level': 0, 'recursive': False},
                                     'POP': {'level': 0, 'recursive': False},
                                     'RSHIFT': {'level': 1, 'recursive': False},
                                     'LSHIFT': {'level': 1, 'recursive': False},
                                     #'PARTITION_UPDATE': {'level': 1, 'recursive': False},
                                     #'COMPSWAP': {'level': 1, 'recursive': False},
                                     'COMPSWAP_PARTITION': {'level':1, 'recursive': False},
                                     'RESET': {'level': 2, 'recursive': False},
                                     'PARTITION': {'level': 2, 'recursive': False},
                                     'QUICKSORT': {'level': 3, 'recursive': False}}.items()))
            for idx, key in enumerate(sorted(list(self.programs_library.keys()))):
                self.programs_library[key]['index'] = idx

            self.prog_to_func = OrderedDict(sorted({'STOP': self._stop,
                                 'PTR_1_LEFT': self._ptr_1_left,
                                 'PTR_2_LEFT': self._ptr_2_left,
                                 'PTR_1_RIGHT': self._ptr_1_right,
                                 'PTR_2_RIGHT': self._ptr_2_right,
                                 'PTR_3_LEFT': self._ptr_3_left,
                                 'PTR_3_RIGHT': self._ptr_3_right,
                                 'PUSH': self._push,
                                 'POP': self._pop,
                                 'SWAP': self._swap,
                                 'SWAP_2': self._swap_2,
                                 'SWAP_3': self._swap_3}.items()))

            self.prog_to_precondition = OrderedDict(sorted({'STOP': self._stop_precondition,
                                         'RSHIFT': self._rshift_precondition,
                                         'LSHIFT': self._lshift_precondition,
                                         'PUSH': self._push_precondition,
                                         'POP': self._pop_precondition,
                                         #'COMPSWAP': self._compswap_precondition,
                                         'COMPSWAP_PARTITION': self._compswap_partition_precondition,
                                         'RESET': self._reset_precondition,
                                         'PARTITION': self._partition_precondition,
                                         'QUICKSORT': self._quicksort_precondition,
                                         'PTR_1_LEFT': self._ptr_1_left_precondition,
                                         'PTR_2_LEFT': self._ptr_2_left_precondition,
                                         'PTR_1_RIGHT': self._ptr_1_right_precondition,
                                         'PTR_2_RIGHT': self._ptr_2_right_precondition,
                                         'PTR_3_LEFT': self._ptr_3_left_precondition,
                                         'PTR_3_RIGHT': self._ptr_3_right_precondition,
                                         'SWAP': self._swap_precondition,
                                         'SWAP_2': self._swap_2_precondition,
                                         'SWAP_3': self._swap_3_precondition}.items()))

            self.prog_to_postcondition = OrderedDict(sorted({'RSHIFT': self._rshift_postcondition,
                                          'LSHIFT': self._lshift_postcondition,
                                          #'COMPSWAP': self._compswap_postcondition,
                                          'COMPSWAP_PARTITION': self._compswap_partition_postcondition,
                                          'RESET': self._reset_postcondition,
                                          'PARTITION': self._partition_postcondition,
                                          'QUICKSORT': self._quicksort_postcondition}.items()))

        else:
            # In no hierarchy mode, the only non-zero program is Bubblesort

            self.programs_library = {'PTR_1_LEFT': {'level': 0, 'recursive': False},
                                     'STOP': {'level': -1, 'recursive': False},
                                     'PTR_2_LEFT': {'level': 0, 'recursive': False},
                                     'PTR_1_RIGHT': {'level': 0, 'recursive': False},
                                     'PTR_2_RIGHT': {'level': 0, 'recursive': False},
                                     'SWAP': {'level': 0, 'recursive': False},
                                     'BUBBLESORT': {'level': 1, 'recursive': False}}
            for idx, key in enumerate(sorted(list(self.programs_library.keys()))):
                self.programs_library[key]['index'] = idx

            self.prog_to_func = {'STOP': self._stop,
                                 'PTR_1_LEFT': self._ptr_1_left,
                                 'PTR_2_LEFT': self._ptr_2_left,
                                 'PTR_1_RIGHT': self._ptr_1_right,
                                 'PTR_2_RIGHT': self._ptr_2_right,
                                 'SWAP': self._swap}

            self.prog_to_precondition = {'STOP': self._stop_precondition,
                                         'BUBBLESORT': self._bubblesort_precondition,
                                         'PTR_1_LEFT': self._ptr_1_left_precondition,
                                         'PTR_2_LEFT': self._ptr_2_left_precondition,
                                         'PTR_1_RIGHT': self._ptr_1_right_precondition,
                                         'PTR_2_RIGHT': self._ptr_2_right_precondition,
                                         'SWAP': self._swap_precondition}

            self.prog_to_postcondition = {'BUBBLESORT': self._bubblesort_postcondition}

        super(QuickSortListEnv, self).__init__(self.programs_library, self.prog_to_func,
                                               self.prog_to_precondition, self.prog_to_postcondition)

    def _ptr_1_left(self):
        """Move pointer 1 to the left."""
        if self.p1_pos > 0:
            self.p1_pos -= 1

    def _ptr_1_left_precondition(self):
        return self.p1_pos > 0

    def _stop(self):
        """Do nothing. The stop action does not modify the environment."""
        pass

    def _stop_precondition(self):
        return True

    def _ptr_2_left(self):
        """Move pointer 2 to the left."""
        if self.p2_pos > 0:
            self.p2_pos -= 1

    def _ptr_2_left_precondition(self):
        return self.p2_pos > 0

    def _ptr_1_right(self):
        """Move pointer 1 to the right."""
        if self.p1_pos < (self.length - 1):
            self.p1_pos += 1

    def _ptr_1_right_precondition(self):
        return self.p1_pos < self.length-1

    def _ptr_2_right(self):
        """Move pointer 2 to the right."""
        if self.p2_pos < (self.length - 1):
            self.p2_pos += 1

    def _ptr_2_right_precondition(self):
        return self.p2_pos < self.length-1

    def _ptr_3_left(self):
        """Move pointer 3 to the right."""
        if self.p3_pos > 0:
            self.p3_pos -= 1

    def _ptr_3_left_precondition(self):
        return self.p3_pos > 0

    def _ptr_3_right(self):
        """Move pointer 3 to the right."""
        if self.p3_pos < (self.length - 1):
            self.p3_pos += 1

    def _ptr_3_right_precondition(self):
        return self.p3_pos < self.length-1

    def _swap(self):
        """Swap the elements pointed by pointers 1 and 2."""
        self.scratchpad_ints[[self.p1_pos, self.p2_pos]] = self.scratchpad_ints[[self.p2_pos, self.p1_pos]]

    def _swap_precondition(self):
        return self.p1_pos != self.p2_pos

    def _swap_2(self):
        """Swap the elements pointed by pointers 2 and 3."""
        self.scratchpad_ints[[self.p2_pos, self.p3_pos]] = self.scratchpad_ints[[self.p3_pos, self.p2_pos]]

    def _swap_2_precondition(self):
        return self.p2_pos != self.p3_pos

    def _swap_3(self):
        """Swap the elements pointed by pointers 3 and 1."""
        self.scratchpad_ints[[self.p3_pos, self.p1_pos]] = self.scratchpad_ints[[self.p1_pos, self.p3_pos]]

    def _swap_3_precondition(self):
        return self.p3_pos != self.p1_pos

    def _push(self):
        """Push the pointers positions inside the stack"""
        assert self._push_precondition(), 'precondition not verified'
        if (self.p3_pos+1 < self.p2_pos):
            self.prog_stack.append(self.p3_pos+1)
            self.prog_stack.append(self.p2_pos)
            self.prog_stack.append(self.p3_pos+1)
        if (self.p3_pos-1 > 0):
            self.prog_stack.append(self.p1_pos)
            self.prog_stack.append(self.p3_pos-1)
            self.prog_stack.append(self.p1_pos)

    def _push_precondition(self):
        return True

    def _pop(self):
        """Pop the first three element of the stack ad initialize pointers with them"""
        #assert self._pop_precondition(), "precondition not verified."
        if len(self.prog_stack) >= 3:
            self.p1_pos = self.prog_stack.pop()
            self.p2_pos = self.prog_stack.pop()
            self.p3_pos = self.prog_stack.pop()

    def _pop_precondition(self):
        return len(self.prog_stack) >= 3

    def _compswap_precondition(self):
        print(self.p1_pos, self.p2_pos, self.p3_pos)
        bool = self.p1_pos < self.length-1
        bool &= self.p2_pos == self.p1_pos or self.p2_pos == (self.p1_pos + 1)
        return bool

    def _lshift_precondition(self):
        return self.p1_pos > 0 or self.p2_pos > 0 or self.p3_pos > 0

    def _rshift_precondition(self):
        return self.p1_pos < self.length-1 or self.p2_pos < self.length-1 or self.p3_pos < self.length-1

    def _bubble_precondition(self):
        bool = self.p1_pos == 0
        bool &= ((self.p2_pos == 0) or (self.p2_pos == 1))
        return bool

    def _reset_precondition(self):
        bool = True
        return bool

    def _bubblesort_precondition(self):
        bool = self.p1_pos == 0
        bool &= self.p2_pos == 0
        return bool

    def _compswap_partition_precondition(self):
        bool = self.p1_pos <= self.p2_pos
        bool &= self.p3_pos == self.p1_pos
        return bool

    def _partition_precondition(self):
        bool = self.p1_pos <= self.p2_pos
        bool &= self.p3_pos == self.p1_pos
        return bool

    def _quicksort_precondition(self):
        bool = self.p1_pos == 0
        bool &= self.p2_pos == self.length-1
        bool &= self.p3_pos == 0
        return bool

    def _compswap_postcondition(self, init_state, state):
        new_scratchpad_ints, new_p1_pos, new_p2_pos, new_p3_pos, new_stack = init_state
        new_scratchpad_ints = np.copy(new_scratchpad_ints)
        if new_p1_pos == new_p2_pos and new_p2_pos < self.length-1:
            new_p2_pos += 1
        idx_left = min(new_p1_pos, new_p2_pos)
        idx_right = max(new_p1_pos, new_p2_pos)
        if new_scratchpad_ints[idx_left] > new_scratchpad_ints[idx_right]:
            new_scratchpad_ints[[idx_left, idx_right]] = new_scratchpad_ints[[idx_right, idx_left]]
        new_state = (new_scratchpad_ints, new_p1_pos, new_p2_pos, new_p3_pos, new_stack)
        return self.compare_state(new_state, init_state)

    def _lshift_postcondition(self, init_state, state):
        init_scratchpad_ints, init_p1_pos, init_p2_pos, init_p3_pos, init_stack = init_state
        scratchpad_ints, p1_pos, p2_pos, p3_pos, stack = state
        bool = np.array_equal(init_scratchpad_ints, scratchpad_ints)
        bool = (init_stack == stack)
        if init_p1_pos > 0:
            bool &= p1_pos == (init_p1_pos-1)
        else:
            bool &= p1_pos == init_p1_pos
        if init_p2_pos > 0:
            bool &= p2_pos == (init_p2_pos-1)
        else:
            bool &= p2_pos == init_p2_pos
        if init_p3_pos > 0:
            bool &= p3_pos == (init_p3_pos-1)
        else:
            bool &= p3_pos == init_p3_pos
        return bool

    def _rshift_postcondition(self, init_state, state):
        init_scratchpad_ints, init_p1_pos, init_p2_pos, init_p3_pos, init_stack = init_state
        scratchpad_ints, p1_pos, p2_pos, p3_pos, stack = state
        bool = np.array_equal(init_scratchpad_ints, scratchpad_ints)
        bool &= (init_stack == stack)
        if init_p1_pos < self.length-1:
            bool &= p1_pos == (init_p1_pos+1)
        else:
            bool &= p1_pos == init_p1_pos
        if init_p2_pos < self.length-1:
            bool &= p2_pos == (init_p2_pos+1)
        else:
            bool &= p2_pos == init_p2_pos
        if init_p3_pos < self.length-1:
            bool &= p3_pos == (init_p3_pos+1)
        else:
            bool &= p3_pos == init_p3_pos
        return bool

    def _reset_postcondition(self, init_state, state):
        init_scratchpad_ints, init_p1_pos, init_p2_pos, init_p3_pos, init_stack = init_state
        scratchpad_ints, p1_pos, p2_pos, p3_pos, stack = state
        bool = np.array_equal(init_scratchpad_ints, scratchpad_ints)
        bool &= (init_stack == stack)
        bool &= (p1_pos == 0 and p2_pos == 0 and p3_pos == 0)
        return bool

    def _bubblesort_postcondition(self, init_state, state):
        scratchpad_ints, p1_pos, p2_pos, p3_pos, stack = state
        # check if list is sorted
        return np.all(scratchpad_ints[:self.length-1] <= scratchpad_ints[1:self.length])

    def _bubble_postcondition(self, init_state, state):
        new_scratchpad_ints, new_p1_pos, new_p2_pos, new_p3_pos, stack = init_state
        new_scratchpad_ints = np.copy(new_scratchpad_ints)
        for idx in range(0, self.length-1):
            if new_scratchpad_ints[idx+1] < new_scratchpad_ints[idx]:
                new_scratchpad_ints[[idx, idx+1]] = new_scratchpad_ints[[idx+1, idx]]
        # bubble is expected to terminate with both pointers at the extreme left of the list
        new_p1_pos = self.length-1
        new_p2_pos = self.length-1
        new_state = (new_scratchpad_ints, new_p1_pos, new_p2_pos, new_p3_pos, stack)
        return self.compare_state(state, new_state)

    def _partition(arr, l, h, j):
        temp_l = l
        x = arr[h]
        while(j<h):
            if arr[j] <= x:
                arr[[j, l]] = arr[[l, j]]
                l += 1
            j += 1
        arr[[l,h]] = arr[[h,l]]
        return arr, temp_l, h, l

    def _compswap_partition_postcondition(self, init_state, state):
        new_scratchpad_ints, new_p1_pos, new_p2_pos, new_p3_pos, stack = init_state
        new_scratchpad_ints = np.copy(new_scratchpad_ints)
        for idx in range(new_p1_pos, new_p2_pos):
            if new_scratchpad_ints[idx] < new_scratchpad_ints[new_p2_pos]:
                new_p1_pos += 1
                new_scratchpad_ints[[new_p1_pos, idx]] = new_scratchpad_ints[[idx, new_p1_pos]]
        # bubble is expected to terminate with both pointers at the extreme left of the list
        new_p3_pos = new_p2_pos-1
        new_state = (new_scratchpad_ints, new_p1_pos, new_p2_pos, new_p3_pos, stack)
        return self.compare_state(state, new_state)

    def _partition_postcondition(self, init_state, state):
        new_scratchpad_ints, new_p1_pos, new_p2_pos, new_p3_pos, stack = init_state
        new_scratchpad_ints = np.copy(new_scratchpad_ints)
        arr, l, h, j = _partition(new_scratchpad_ints)
        new_p1_pos = l
        new_p2_pos = h
        new_p3_pos = j
        new_state = (arr, new_p1_pos, new_p2_pos, new_p3_pos, stack)
        return self.compare_state(state, new_state)

    def _quicksort_postcondition(self, init_state, state):
        scratchpad_ints, p1_pos, p2_pos, p3_pos, stack = state
        # check if list is sorted
        return np.all(scratchpad_ints[:self.length-1] <= scratchpad_ints[1:self.length])

    def _one_hot_encode(self, digit, basis=10):
        """One hot encode a digit with basis.

        Args:
          digit: a digit (integer between 0 and 9)
          basis:  (Default value = 10)

        Returns:
          a numpy array representing the 10-hot-encoding of the digit

        """
        encoding = np.zeros(basis)
        encoding[digit] = 1
        return encoding

    def _one_hot_decode(self, one_encoding):
        """Returns digit associated to a one hot encoding.

        Args:
          one_encoding: numpy array representing the 10-hot-encoding of a digit.

        Returns:
          the digit encoded in one_encoding

        """
        return np.argmax(one_encoding)

    def reset_env(self):
        """Reset the environment. The list are values are draw randomly. The pointers are initialized at position 0
        (at left position of the list).

        """
        self.scratchpad_ints = np.random.randint(10, size=self.length)
        self.prog_stack = list(np.random.randint(self.length-1, size=3*(self.length%2)))
        current_task_name = self.get_program_from_index(self.current_task_index)
        if current_task_name == 'BUBBLE' or current_task_name == 'BUBBLESORT':
            init_pointers_pos1 = 0
            init_pointers_pos2 = 0
            init_pointers_pos3 = 0
        elif current_task_name == 'PARTITION' or current_task_name == "COMPSWAP_PARTITION":
            while True:
                init_pointers_pos2 = int(np.random.randint(0, self.length))
                if not (init_pointers_pos2 == 0):
                    break
            init_pointers_pos1 = int(np.random.randint(0, init_pointers_pos2))
            init_pointers_pos3 = init_pointers_pos1
        elif current_task_name == 'QUICKSORT':
            init_pointers_pos1 = 0
            init_pointers_pos2 = self.length-1
            init_pointers_pos3 = 0
        elif current_task_name == 'RESET':
            while True:
                init_pointers_pos1 = int(np.random.randint(0, self.length))
                init_pointers_pos2 = int(np.random.randint(0, self.length))
                init_pointers_pos3 = int(np.random.randint(0, self.length))
                if not (init_pointers_pos1 == 0 and init_pointers_pos2 == 0 and init_pointers_pos3 == 0):
                    break
        elif current_task_name == 'LSHIFT':
            while True:
                init_pointers_pos1 = int(np.random.randint(0, self.length))
                init_pointers_pos2 = int(np.random.randint(0, self.length))
                init_pointers_pos3 = int(np.random.randint(0, self.length))
                if not (init_pointers_pos1 == 0 and init_pointers_pos2 == 0 and init_pointers_pos3 == 0):
                    break
        elif current_task_name == 'RSHIFT':
            while True:
                init_pointers_pos1 = int(np.random.randint(0, self.length))
                init_pointers_pos2 = int(np.random.randint(0, self.length))
                init_pointers_pos3 = int(np.random.randint(0, self.length))
                if not (init_pointers_pos1 == self.length - 1 and init_pointers_pos2 == self.length - 1 and init_pointers_pos3 == self.length-1):
                    break
        elif current_task_name == 'COMPSWAP':
            init_pointers_pos1 = int(np.random.randint(0, self.length - 1))
            init_pointers_pos2 = int(np.random.choice([init_pointers_pos1, init_pointers_pos1 + 1]))
            init_pointers_pos3 = 0
        else:
            raise NotImplementedError('Unable to reset env for this program...')

        self.p1_pos = init_pointers_pos1
        self.p2_pos = init_pointers_pos2
        self.p3_pos = init_pointers_pos3
        self.has_been_reset = True

    def get_state(self):
        """Returns the current state.

        Returns:
            the environment state

        """
        assert self.has_been_reset, 'Need to reset the environment before getting states'
        return np.copy(self.scratchpad_ints), self.p1_pos, self.p2_pos, self.p3_pos, self.prog_stack.copy()

    def get_observation(self):
        """Returns an observation of the current state.

        Returns:
            an observation of the current state
        """
        assert self.has_been_reset, 'Need to reset the environment before getting observations'

        p1_val = self.scratchpad_ints[self.p1_pos]
        p2_val = self.scratchpad_ints[self.p2_pos]
        p3_val = self.scratchpad_ints[self.p3_pos]
        is_sorted = int(self._is_sorted())
        is_stack_empty = int(len(self.prog_stack) >= 3)
        pointers_same_pos = int(self.p1_pos == self.p2_pos)
        pointers_same_pos_2 = int(self.p2_pos == self.p3_pos)
        pt_1_left = int(self.p1_pos == 0)
        pt_2_left = int(self.p2_pos == 0)
        pt_1_right = int(self.p1_pos == (self.length - 1))
        pt_2_right = int(self.p2_pos == (self.length - 1))
        pt_3_left = int(self.p3_pos == 0)
        pt_3_right = int(self.p3_pos == (self.length - 1))
        p1p2p3 = np.eye(10)[[p1_val, p2_val, p3_val]].reshape(-1)
        bools = np.array([
            pt_1_left,
            pt_1_right,
            pt_2_left,
            pt_2_right,
            pt_3_left,
            pt_3_right,
            pointers_same_pos,
            pointers_same_pos_2,
            is_sorted,
            is_stack_empty
        ])
        return np.concatenate((p1p2p3, bools), axis=0)

    def get_observation_dim(self):
        """

        Returns:
            the size of the observation tensor
        """
        return 3 * 10 + 10

    def reset_to_state(self, state):
        """

        Args:
          state: a given state of the environment
        reset the environment is the given state

        """
        self.scratchpad_ints = state[0].copy()
        self.p1_pos = state[1]
        self.p2_pos = state[2]
        self.p3_pos = state[3]
        self.prog_stack = state[4]

    def _is_sorted(self):
        """Assert is the list is sorted or not.

        Args:

        Returns:
            True if the list is sorted, False otherwise

        """
        arr = self.scratchpad_ints
        return np.all(arr[:-1] <= arr[1:])

    def get_state_str(self, state):
        """Print a graphical representation of the environment state"""
        scratchpad = state[0].copy()  # check
        p1_pos = state[1]
        p2_pos = state[2]
        p3_pos = state[3]
        stack = state[4]
        str = 'list: {}, p1 : {}, p2 : {}, p3: {}, stack: {}'.format(scratchpad, p1_pos, p2_pos, p3_pos, stack)
        return str

    def compare_state(self, state1, state2):
        """
        Compares two states.

        Args:
            state1: a state
            state2: a state

        Returns:
            True if both states are equals, False otherwise.

        """
        bool = True
        bool &= np.array_equal(state1[0], state2[0])
        bool &= (state1[1] == state2[1])
        bool &= (state1[2] == state2[2])
        bool &= (state1[3] == state2[3])
        bool &= (state1[4] == state2[4])
        return bool
