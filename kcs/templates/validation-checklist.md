# KCS Validation Checklist

Used by the `/validate` phase to verify the draft against the KCS Content Standard.
Each item must pass. Failures are reported with the section and specific issue.

## Structure

- [ ] Metadata block is present (Article Type, Article Confidence, Product)
- [ ] Title section is present and non-empty
- [ ] Issue section is present and non-empty
- [ ] Environment section is present and non-empty
- [ ] Diagnostic Steps section is present and non-empty
- [ ] Resolution section is present and non-empty
- [ ] Root Cause section is present and non-empty

## Title

- [ ] Describes the main symptom and includes the product name
- [ ] One liner — short enough to be scannable as a single line
- [ ] No brackets around product names
- [ ] No article type prefix ("Solution:", "KCS:", etc.)

## Issue

- [ ] Describes the problem from the customer's perspective
- [ ] Error messages are in backticks or fenced code blocks
- [ ] Does not describe the workaround (that belongs in Resolution)
- [ ] No internal Jira links or internal tool references

## Environment

- [ ] Lists product name and version
- [ ] Uses official product names, not internal shorthand
- [ ] One product per bullet point

## Diagnostic Steps

- [ ] Uses numbered steps
- [ ] Each step has a single action
- [ ] Commands are in fenced code blocks
- [ ] Placeholders use `<UPPERCASE_WITH_UNDERSCORES>` format
- [ ] No internal Jira links or internal tool references

## Resolution

- [ ] Workarounds are explicitly labeled as "Workaround"
- [ ] Uses numbered steps for sequential actions
- [ ] Commands are in fenced code blocks
- [ ] Placeholders use `<UPPERCASE_WITH_UNDERSCORES>` format and are consistent with Diagnostic Steps
- [ ] Ends with a verification step
- [ ] No internal Jira links or internal tool references

## Root Cause

- [ ] Explains the technical mechanism behind the issue
- [ ] Jira link is present if a permanent fix is tracked (acceptable in this section only)

## Style

- [ ] Present tense throughout ("The device shows..." not "The device showed...")
- [ ] No personal pronouns ("I", "me", "we", "myself")
- [ ] Backticks used for file paths, command names, configuration keys, and technical terms
- [ ] Fenced code blocks used for full commands and example output
- [ ] Numbered steps for sequential actions, bullet points for non-sequential items
- [ ] en-US English spelling
- [ ] No "To be determined" placeholders remaining — except Root Cause, which may remain TBD if the user has explicitly acknowledged it
