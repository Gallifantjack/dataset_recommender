from .ingredients import Ingredients
from typing import Union


class Selector():
    """Class responsible for selecting the variables affected by a recipe step
    
    Args:
        description (str): text used to represent Selector when printed in summaries
        names (Union[str, list[str]]): column names to select
        roles (Union[str, list[str]]): column roles to select, see also Ingredients
        types (Union[str, list[str]]): column data types to select
    """
    def __init__(
        self, 
        description: str, 
        names: Union[str, list[str]]=None, 
        roles: Union[str, list[str]]=None, 
        types: Union[str, list[str]]=None
    ):
        self.description = description
        self.set_names(names)
        self.set_roles(roles)
        self.set_types(types)

    def set_names(self, names: Union[str, list[str]]):
        """Set the column names to select with this Selector

        Args:
            names (Union[str, list[str]]): column names to select
        """
        self.names = enlist_str(names)

    def set_roles(self, roles: Union[str, list[str]]):
        """Set the column roles to select with this Selector

        Args:
            roles (Union[str, list[str]]): column roles to select, see also Ingredients
        """
        self.roles = enlist_str(roles)

    def set_types(self, roles: Union[str, list[str]]):
        """Set the column data types to select with this Selector

        Args:
            roles (Union[str, list[str]]): column data types to select
        """
        self.types = enlist_str(roles)

    def __call__(self, ingr: Ingredients) -> list[str]:
        """Select variables from Ingredients

        Args:
            ingr (Ingredients): object from which to select the variables

        Raises:
            TypeError: when something other than an Ingredient object is passed

        Returns:
            list[str]: selected variables
        """
        
        if not isinstance(ingr, Ingredients):
            raise TypeError(f'Expected Ingredients, got {ingr.__class__}')
        
        vars = ingr.columns.tolist()

        if self.roles is not None:
            sel_roles = [v for v, r in ingr.roles.items() if len(intersection(r, self.roles)) > 0]
            vars = intersection(vars, sel_roles)

        if self.types is not None:
            # currently matches types by name. is this problematic?
            sel_types = [v for v, t in ingr.dtypes.items() if t.name in self.types]
            vars = intersection(vars, sel_types)

        if self.names is not None:
            vars = intersection(vars, self.names)

        return vars

    def __repr__(self):
        return self.description

def enlist_str(x: Union[str, list[str], None]) -> Union[list[str], None]:
    """Wrap a str in a list if it isn't a list yet

    Args:
        x (Union[str, list[str], None]): object to wrap.

    Raises:
        TypeError: If neither a str nor a list of strings is passed

    Returns:
        Union[list[str], None]: _description_
    """
    if isinstance(x, str):
        return [x]
    elif isinstance(x, list):
        if not all(isinstance(i, str) for i in x):
            raise TypeError('Only lists of str are allowed.')
        return x
    elif x is None:
        return x
    else:
        raise TypeError(f'Expected str or list of str, got {x.__class__}')

def intersection(x: list, y: list) -> list:
    """Intersection of two lists

    Note: 
        maintains the order of the first list
        does not deduplicate items (i.e., does not return a set)

    Args:
        x (list): first list
        y (list): second list

    Returns:
        list: elements in `x` that are also in `y`
    """
    if isinstance(x, str):
        x = [x]
    if isinstance(y, str):
        y = [y]
    return [i for i in x if i in y]


def all_of(names: Union[str, list[str]]) -> Selector:
    """Select any columns with one of the given names

    Args:
        names (Union[str, list[str]]): names to select

    Returns:
        Selector: object representing the selection rule
    """
    return Selector(description=str(names), names=names)


def starts_with(pattern):
    raise NotImplementedError()


def ends_with(pattern):
    raise NotImplementedError()


def contains(pattern):
    raise NotImplementedError()


def has_role(roles: Union[str, list[str]]) -> Selector:
    """Select any columns with one of the given roles

    Args:
        roles (Union[str, list[str]]): roles to select

    Returns:
       Selector: object representing the selection rule
    """
    return Selector(description=f'roles: {roles}', roles=roles)


def has_type(types: Union[str, list[str]]) -> Selector:
    """Select any columns with one of the given types

    Args:
        types (Union[str, list[str]]): data types to select
    
    Note: 
        Data types are selected based on string representation as returned 
        by `df[[varname]].dtype.name`

    Returns:
        Selector: object representing the selection rule
    """
    return Selector(description=f'types: {types}', types=types)


def groups() -> Selector:
    """Select any grouping variables

    Returns:
        Selector: object representing the selection rule
    """
    return Selector(description=f'grouping variables', roles=['group'])


def all_predictors() -> Selector:
    """Select all predictor columns

    Returns:
        Selector: object representing the selection rule
    """
    sel = has_role(['predictor'])
    sel.description = 'all predictors'
    return sel


def all_numeric_predictors() -> Selector:
    """Select all numerical predictor columns

    Returns:
        Selector: object representing the selection rule
    """
    sel = all_predictors()
    sel.set_types(['int16', 'int32', 'int64', 'float16', 'float32', 'float64'])
    sel.description = 'all numeric predictors'
    return sel


def all_outcomes() -> Selector:
    """Select outcome columns

    Returns:
        Selector: object representing the selection rule
    """
    sel = has_role(['outcome'])
    sel.description = 'all outcomes'
    return sel
