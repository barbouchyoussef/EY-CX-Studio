"""One module per feature area. Routes resolve a service, check access, delegate.

They deliberately contain no business logic -- anything a second caller could ever need belongs
in `app/services/` instead.
"""
