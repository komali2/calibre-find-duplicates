# Calibre "Find Duplicates" Plugin with Merge Duplicate Functionality

This is a fork of kiwidude's "Find Duplicates" plugin that allows for merging duplicates.

Merging duplicates can be dangerous, you can lose metadata or versions of a book if you aren't careful. You must use this plugin with care. Take note of the GPL-3 license included: there is no warranty, nothing is guaranteed.

kiwidude did the bulk of the work that makes this possible. You should thank them for their hard work, and take a look at their repository of other really useful Calibre plugins. Developers, kiwidude also has a lot of really interesting information about learning to develop your own Calibre plugins! https://github.com/kiwidude68/calibre_plugins

More information on how this was developed can be found at my blog post. If you're interested in learning how to contribute to an open source project but think you can't because you don't know enough, I recommend reading it! It's more possible than you think: https://blog.calebjay.com/posts/calibre-automerge/

# Usage

To install this plugin, follow the Calibre instructions: https://manual.calibre-ebook.com/creating_plugins.html . In short:

1. Back up your library. Merging duplicates is *a file destructive action.* You risk *losing your actual ebook files*.
2. Download this repo
3. Open a terminal at the root of this folder (the same directory as this README)
4. Run `calibre-customize -b .`
5. Open Calibre
6. Under Preferences > Plugins > User interface action, click "Find Duplicates Merge Fork"
7. Click "customize plugin." A window should pop up with options such as "Keyboard shortcuts..." If not, something broke, and you should try to debug this or email me (this project is low priority for me, your best chance of fixing it is by yourself).
8. If step 6 worked, then, close the Preferences window, then open Preferences > Toolbars & menu.
9. Click "the main toolbar" in the dropdown
10. Using the tool, add "Find Duplicates" to the "Current Actions" box on the right. Click "apply" afterwards.
11. A "Find Duplicates" button should now be on your toolbar. Click it, or click the dropdown indicator next to it to customize your duplicate find search.
12. A list of "groups" of duplicates should be displayed, if your search was configured correctly. If not, try looking for instructions on kiwidude's repo, linked above. Remember, the bulk of why this works at all is thanks to their work. A "group" is a list of entries in Calibre's database that, hopefully, all refer to the "same book." Each of these entries may refer to multiple actual files, of various formats. This is important, because if for example two entries have a `pdf` format, *only the pdf of the first entry will exist after merging!* This is the built in way that the Calibre merge tool works.
13. Also note that when merging, books will be merged into the *first* entry in a given group. I'm not sure how to change this functionality, or what ways there are of changing which entry is considered the "first" entry - for example, simply sorting on different columns may not actually change which entry is considered the "first" entry. This is why it's very important you back up your library! Your results may be unexpected and disastrous.
14. A final note, the merge function uses the `merge_only_formats` flag of Calibre's merge tool. That means that no metadata will be copied from one entry in a group to another, the only thing that will be merged are *formats*. So if there are two entries, one having a pdf format, and another having an epub format, these will be merged into one entry with a pdf and epub format. The remaining metadata will be whatever the metadata was for the first entry. If you want to change this behavior, you'll need to modify the flags on line `452` in `duplicates.py` in this repo.
15. When you're ready, click the "Find Duplicates" icon dropdown, and select "Merge All Groups."
16. From here, follow the Calibre merge tool's prompts, which are not a part of this repo or kiwidude's work, these are built-in Calibre tools.
