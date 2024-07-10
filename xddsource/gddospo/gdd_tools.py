import re

def repotest(string):
    """Check to see if a repository is referenced in the paper.

    string A character string returned from geodeepdive highlights.
    returns None or the string matched.
    """
    test = re.search(r'((github)|(gitlab)|(bitbucket)).com\/((\s{0,1})[\w,\-,\_]+\/*){1,2}', string)
    if test is None:
        output = {'repo': None, 'highlight': string}
    else:
        test_no_space = re.sub('\s', '', test[0])
        test_no_punct = re.sub('[^\w\s]$', '', test_no_space)
        output = {'repo': test_no_punct, 'highlight': string}
    return output

def empty_none(val):
    """Clean out None values.

    val A Python object that may or may not have None values.
    returns a Python object with all None values replaced by ''.
    """
    for k in val.keys():
        if isinstance(val[k], dict):
            empty_none(val[k])
        else:
            if val[k] is None:
                val[k] = ''
    return val
