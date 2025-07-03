# API

- Check that if the past beacon to be triggered has is_first_when_entering set to true, and the current beacon has got it set to false, and they're from the same shipyard, then the person is entering.
- Check that if the past beacon to be triggered has is_first_when_entering set to false, and the current beacon has got it set to true, and they're from the same shipyard, then the person is exiting.
- Check that if the past beacon is from another shipyard than the current one, then the advertisement is ignored.
- Check that if the past beacon is the same as the current one, then the advertisement is ignored.
- Check that if either the past or the current beacon don't exist in the table, then the advertisement is ignored.
- Check that if the adverisement has past activator id equal to 0 then the advertisement is ignored.
- Check that if the tag name of the advertisement is not found in the table then a new tag row is created in the db, taking the information from the advertisement.
- Check that every single advertisement from a tag updates its battery level, even if the advertisement is not valid.
- Check that if the tag of the advertisement hasn't their packet counter already set in the table, then it is set to the one of the advertisement.
- Check that if the packet counter of the advertisement is the same as the value of the tag record, then the advertisement is ignored.
- Check that if the packet counter of the tag record is not the same as the value of the advertisement, then set it equal to the one of the advertisement, and continue processing the advertisement.
- Check that if a person enters, then exits, a log is first created, then it is closed.
- Check that if a person enters, then gets assigned to a new tag, then exits with that new tag, the same log is closed.
- Check that If a person enters, then their exit is not registered by system, and they enter again, two open logs are created. If then this person exits, the more recently created record gets closed, and the older record will never be closed by the system, even if that person were to exit two times in a row.
- Check that if a person exits but all their past logs are closed, a new log that only registers them exiting is created. This record will never be opened by the system, even if that person enters later, but it can be opened manually by an operator
- Check that if an unassigned tag enters an entry is created, likewise for an exiting unassigned tag

# View

- Can apply a filter and show results correctly
- Can apply two filters and show results correctly
- Can modify successfully
- Can make modifications but cancel modifying successfully
- Can create succesfully
- Can cancel creation successfully
- Well put "no results found" page

For:

- Logs
- Entries
- Tags
- Crew members
- Ships