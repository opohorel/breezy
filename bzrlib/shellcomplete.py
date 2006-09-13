import sys


def shellcomplete(context=None, outfile = None):
    if outfile is None:
        outfile = sys.stdout
    if context is None:
        shellcomplete_commands(outfile = outfile)
    else:
        shellcomplete_on_command(context, outfile = outfile)

def shellcomplete_on_command(cmdname, outfile = None):
    cmdname = str(cmdname)

    if outfile is None:
        outfile = sys.stdout

    from inspect import getdoc
    import commands
    cmdobj = commands.get_cmd_object(cmdname)

    doc = getdoc(cmdobj)
    if doc is None:
        raise NotImplementedError("sorry, no detailed shellcomplete yet for %r" % cmdname)

    shellcomplete_on_option(cmdobj.takes_options, outfile = None)
    for aname in cmdobj.takes_args:
        outfile.write(aname + '\n')


def shellcomplete_on_option(options, outfile=None):
    from bzrlib.option import Option
    if not options:
        return
    if outfile is None:
        outfile = sys.stdout
    for on in options:
        for shortname, longname in Option.SHORT_OPTIONS.items():
            if longname == on:
                l = '"(--' + on + ' -' + shortname + ')"{--' + on + ',-' + shortname + '}'
                break
	    else:
		l = '--' + on
        outfile.write(l + '\n')


def shellcomplete_commands(outfile = None):
    """List all commands"""
    import inspect
    import commands
    from inspect import getdoc
    
    if outfile is None:
        outfile = sys.stdout
    
    cmds = []
    for cmdname, cmdclass in commands.get_all_cmds():
        cmds.append((cmdname, cmdclass))
	for alias in cmdclass.aliases:
	    cmds.append((alias, cmdclass))
    cmds.sort()
    for cmdname, cmdclass in cmds:
        if cmdclass.hidden:
            continue
        doc = getdoc(cmdclass)
        if doc is None:
	    outfile.write(cmdname + '\n')
        else:
	    doclines = doc.splitlines()
	    firstline = doclines[0].lower()
	    outfile.write(cmdname + ':' + firstline[0:-1] + '\n')
