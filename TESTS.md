# API

[ ] Check that if the past beacon to be triggered has is_first_when_entering set to true, and the current beacon has got it set to false, and they're from the same shipyard, then the person is entering.
[ ] Check that if the past beacon to be triggered has is_first_when_entering set to false, and the current beacon has got it set to true, and they're from the same shipyard, then the person is exiting.
[ ] Check that if the past beacon is from another shipyard than the current one, then the advertisement is ignored.
[ ] Check that if the past beacon is the same as the current one, then the advertisement is ignored.
[ ] Check that if either the past or the current beacon don't exist in the table, then the advertisement is ignored.
[ ] Check that if the adverisement has past activator id equal to 0 then the advertisement is ignored.
[ ] Check that if the tag name of the advertisement is not found in the table then the advertisement is ignored.
[ ] Check that every single advertisement from a tag updates its battery level, even if the advertisement is not valid.
[ ] Check that if the tag of the advertisement hasn't their packet counter already set in the table, then it is set to the one of the advertisement.
[ ] Check that if the packet counter of the advertisement is the same as the value of the tag record, then the advertisement is ignored.
[ ] Check that if the packet counter of the tag record is not the same as the value of the advertisement, then set it equal to the one of the advertisement, and continue processing the advertisement.
[ ] Check that if a person enters, then exits, a log is first created, then it is closed.
[ ] Check that if a person enters, then gets assigned to a new tag, then exits with that new tag, the same log is closed.
[ ] Check that If a person enters, then their exit is not registered by system, and they enter again, two open logs are created. If then this person exits, the more recently created record gets closed, and the older record will never be closed by the system, even if that person were to exit two times in a row.
[ ] Check that if a person exits but all their past logs are closed, a new log that only registers them exiting is created. This record will never be opened by the system, even if that person enters later, but it can be opened manually by an operator
[ ] Check that if an unassigned tag enters an entry is created, likewise for an exiting unassigned tag

## Registering tags

In case it is decided that the tags are automatically registered by the system when the advertisement packet is sent, then a set of tests have to be made to assert what happens when the tags are registered.


[ ] Check that a tag is properly registered when sending the first advertisement, and that it is registered not only if the advertisement is a valid log or entry, but that it is registered if an advertisement at all is sent by that tag.
[ ] Check that, after registering the tag, the processing of the advertisement contuinues normally, i.e. that if the advertisement was a valid entry, that the entry is registered properly.
[ ] The second advertisement of a tag has to be considered as such and thus the tag mustn't be registered twice as two separate tags in the database, but only once as one row in the database.



# View

[ ] Can apply a filter and show results correctly
[ ] Can apply two filters and show results correctly
[ ] Can modify successfully
[ ] Can make modifications but cancel modifying successfully
[ ] Can create succesfully
[ ] Can cancel creation successfully
[ ] Well put "no results found" page
[ ] Every single textbox area can't exceed the limit imposed by the database
[ ] Table pagination works properly
[ ] Can delete succesfully

For:

[ ] Logs
[ ] Entries
[ ] Tags
[ ] Crew members
[ ] Ships