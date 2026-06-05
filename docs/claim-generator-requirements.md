# C2PA Claim Generator Requirements

Normative requirements from the C2PA 2.1 specification directed at
claim generators (software that creates C2PA manifests).
Extracted from all specification sections. Organized by spec area.

**Total requirements: 118**

> Rules tagged `(validator too)` apply to both claim generators and validators.

---

## Table of Contents

- [Versioning](#versioning) — 1 rule
- [Assertions](#assertions) — 11 rules
- [Unique Identifiers](#unique-identifiers) — 4 rules
- [Binding to Content](#binding-to-content) — 2 rules
- [Claims](#claims) — 28 rules
- [Manifests](#manifests) — 11 rules
- [Cryptography](#cryptography) — 2 rules
- [Trust Model](#trust-model) — 7 rules
- [Standard Assertions](#standard-assertions) — 52 rules

---

## Versioning

*1 requirement*

### 5.1. Compatibility

**[GEN-VERSIO-0001]** `SHALL NOT`  
In this specification, when a construct is marked as deprecated, that means that a claim generator shall not write that construct (or value), but that a validator should read it.


## Assertions

*11 requirements*

### 6.3. Versioning

**[GEN-ASSERT-0002]** `SHALL`  
Deprecated fields for C2PA standard assertions shall be indicated in Chapter 18, C2PA Standard Assertions.

**[GEN-ASSERT-0004]** `SHALL`  
In those situations where a non-backwards compatible change is required, instead of increasing the label’s version number, the assertion shall be given a new label.

**[GEN-ASSERT-0001]** `SHALL NOT`  
Existing fields shall not be removed.

**[GEN-ASSERT-0003]** `SHALL NOT`  
Claim generators shall not insert data into deprecated assertion fields when creating assertions.

### 6.6. Assertion Store

**[GEN-ASSERT-0005]** `SHALL`  
The assertions and assertion store shall be stored as described in Section 11.1, “Use of JUMBF”; in particular, each assertion referenced in a claim’s created_assertions or gathered_assertions (but not redacted_assertions) shall be present in the assertion store located in the same C2PA Manifest as the claim.

### 6.8. Redaction of Assertions

**[GEN-ASSERT-0006]** `SHALL`  
In addition, a record that something was removed shall be added to the claim in the form of a URI reference to the redaction assertion in the redacted_assertions field of the claim.

**[GEN-ASSERT-0008]** `SHALL`  
When redacting an ingredient assertion that references a C2PA Manifest, the associated manifest shall be removed from the C2PA Manifest Store if no other references to it remain after redacting.

**[GEN-ASSERT-0009]** `SHALL`  
Unless the redaction of the assertion also requires modification to the digital content, an update manifest shall be used to document the redaction as it makes a statement about the non-changes to the content.

**[GEN-ASSERT-0011]** `SHALL`  
They shall also not redact any hard binding to content assertion - either a c2pa.hash.data, c2pa.hash.boxes, c2pa.hash.collection.data, c2pa.hash.bmff.v2 (deprecated), or c2pa.hash.bmff.v3, as these assertions are necessary for determining the integrity of the asset.

**[GEN-ASSERT-0010]** `SHALL NOT`  
Claim generators shall not redact assertions with a label of c2pa.actions or c2pa.actions.v2 as this assertion type represents essential information in understanding the history of an asset.

**[GEN-ASSERT-0007]** `SHOULD`  
It is also strongly recommended that the claim generator should add a c2pa.redacted action assertion with a redacted field as described in Section 18.12.5, “Parameters”.


## Unique Identifiers

*4 requirements*

### 8.2. Versioning Manifests Due to Conflicts

**[GEN-UNIQUE-0001]** `MUST`  
In such a case, the modified version of the ingredient manifest needs to be copied into the asset’s C2PA Manifest Store, but must be re-labeled.

**[GEN-UNIQUE-0002]** `SHALL`  
If the current URN does not contain a "Claim Generator identifier string", then the claim generator shall append a :.

**[GEN-UNIQUE-0003]** `SHALL`  
In all cases, the claim generator shall append a : to the URN followed by a monotonically increasing integer, starting with 1, followed by an underscore (_) and then an integer from the list below representing the reason for the re-labeling.

### 8.3. Identifying Non-C2PA Assets

**[GEN-UNIQUE-0004]** `MAY`  
When working with assets that do not contain a C2PA Manifest and do not contain embedded XMP, the claim generator may use any method of its choosing to provide it with a unique identifier.


## Binding to Content

*2 requirements*

### 9.3. Soft Bindings

**[GEN-BINDIN-0001]** `SHALL NOT`  
Because they serve a different purpose, a soft binding shall not be used as a hard binding.

### 9.3.1. List of Allowed Soft Binding Algorithms

**[GEN-BINDIN-0002]** `SHALL`  
All soft bindings shall be generated using one of the algorithms listed in the soft binding algorithm list as supported by this specification.


## Claims

*28 requirements*

### 10.1. Overview

**[GEN-CLAIMS-0001]** `SHOULD NOT`  
Validators shall still accept this label (and associated claim-map), but claim generators should not produce such a claim.

### 10.2.3.1. General

**[GEN-CLAIMS-0002]** `SHALL`  
Detailed information about the claim generator shall be present as the value of claim_generator_info.

### 10.2.3.2. Generator Info Map

**[GEN-CLAIMS-0003]** `MAY`  
A claim generator may desire to provide a graphical representation of itself, referred here as an icon, to a Manifest Consumer that is presenting a user experience.

### 10.3.2.1. Adding Assertions and Redactions

**[GEN-CLAIMS-0004]** `SHALL`  
The claim shall contain a created_assertions field and may contain a gathered_assertions field.

**[GEN-CLAIMS-0005]** `SHALL`  
In a standard or time-stamp manifest, the created_assertions field’s value shall include at least one assertion that represents a hard binding.

**[GEN-CLAIMS-0006]** `SHALL`  
If any assertions in ingredient claims are being redacted, their URI references shall be added to list which is the value of the redacted_assertions field.

### 10.3.2.2. Adding Ingredients

**[GEN-CLAIMS-0007]** `SHALL`  
When an ingredient contains one or more C2PA manifests, those manifests shall be inserted into this asset’s C2PA Manifest Store to ensure that the provenance data is kept intact.

**[GEN-CLAIMS-0008]** `SHALL`  
If a manifest with the same unique identifier is already present in the C2PA Manifest Store, the two shall be compared (via hashing).

**[GEN-CLAIMS-0009]** `SHALL`  
If they are identical, the new manifest shall be ignored.

**[GEN-CLAIMS-0010]** `SHALL`  
If they are different, the new manifest shall be added to the store after changing its unique identifier to a new value as described in Chapter 8, Unique Identifiers.

### 10.3.2.4. Signing a Claim

**[GEN-CLAIMS-0011]** `SHALL`  
For standard and update manifests, the payload field of Sig_structure shall be the serialized CBOR of the claim document, and shall use detached content mode.

**[GEN-CLAIMS-0012]** `SHALL`  
For time-stamp manifests, the payload field of Sig_structure shall be the value of the signature field of the COSE_Sign1_Tagged structure contained in the C2PA Claim Signature box of the C2PA Manifest of its parent ingredient, and shall use detached content mode.

### 10.3.2.5.2. Choosing the Payload

**[GEN-CLAIMS-0013]** `SHALL NOT` *(validator too)*  
A claim generator shall not create one, but a validator shall process one if present.

### 10.3.2.5.3. Obtaining the time-stamp

**[GEN-CLAIMS-0014]** `SHALL`  
All time-stamps shall be obtained as described in RFC 3161 with the following additional requirements:

**[GEN-CLAIMS-0015]** `SHALL`  
The MessageImprint of the TimeStampReq structure (RFC 3161, section 2.4.1) shall be computed by creating the ToBeSigned value in RFC 8152, section 4.4, with the following values for elements of Sig_structure:

**[GEN-CLAIMS-0016]** `SHALL`  
The context element shall be CounterSignature.

**[GEN-CLAIMS-0017]** `SHALL`  
The payload element shall be the value described by Section 10.3.2.5.2, “Choosing the Payload”.

**[GEN-CLAIMS-0018]** `SHALL`  
The certReq boolean of the TimeStampReq structure shall be asserted in the request to the TSA, to ensure its certificate chain is provided in the response.

### 10.3.2.5.4. Storing the time-stamp

**[GEN-CLAIMS-0019]** `SHALL`  
If present, the value of this header shall be a tstContainer defined by Example 2, “CDDL for tstContainer”.

**[GEN-CLAIMS-0020]** `SHALL`  
The content of the TimeStampResp structure received in reply from the TSA shall be stored as the value of the val property of an element of tstTokens.

**[GEN-CLAIMS-0021]** `SHALL`  
v2 time-stamps shall be stored in a COSE unprotected header whose label is the string sigTst2.

**[GEN-CLAIMS-0022]** `SHALL`  
When present, the value of this header shall be a tstContainer defined by Example 2, “CDDL for tstContainer”.

**[GEN-CLAIMS-0023]** `SHALL`  
The content of value of the timeStampToken field of the TimeStampResp structure received in reply from the TSA shall be stored as the value of the val property of an element of tstTokens.

**[GEN-CLAIMS-0024]** `SHALL`  
If no time-stamps are included, then neither header (sigTst nor sigTst2) shall be present in the COSE unprotected header.

### 10.3.2.6. Credential Revocation Information

**[GEN-CLAIMS-0025]** `SHALL`  
If credential revocation information is attached in this manner, a trusted time-stamp shall also be obtained after signing, as described in Section 10.3.2.5, “Time-stamps”.

### 10.4.1. Create content bindings

**[GEN-CLAIMS-0026]** `SHALL`  
Claim generators shall ensure that changes to pad data (or any other excluded asset data) cannot change how the asset is interpreted.

### 10.4.4. Going back and filling in

**[GEN-CLAIMS-0028]** `SHOULD`  
In this case, claim generators should use padding prior to assertion creation to ensure that the file layout need not change once the assertion has been finalized.

**[GEN-CLAIMS-0027]** `MAY`  
As such, the claim generator may no longer be able to change the file layout and/or offsets in a data hash assertion.


## Manifests

*11 requirements*

### 11.1.4.2. Manifest Store

**[GEN-MANIFE-0001]** `SHALL`  
The C2PA Manifest Store shall have a label of c2pa, a JUMBF type UUID of 63327061-0011-0010-8000-00AA00389B71 (c2pa) and shall contain one or more C2PA manifest superboxes, also known as C2PA Manifests.

**[GEN-MANIFE-0002]** `SHALL`  
Each C2PA Manifest shall contain the data created at the time a claim is issued including the C2PA Assertion Store, a C2PA Claim, and a C2PA Claim Signature.

**[GEN-MANIFE-0003]** `SHALL`  
The JUMBF type UUID for each C2PA Manifest shall be either 63326D61-0011-0010-8000-00AA00389B71 (c2ma), 6332636D-0011-0010-8000-00AA00389B71 (c2cm) or 6332756D-0011-0010-8000-00AA00389B71 (c2um) depending on the type of manifest.

**[GEN-MANIFE-0004]** `SHALL`  
The C2PA Manifest box shall be labelled with a urn:c2pa value computed as described in Unique Identifiers.

### 11.1.4.3. Assertion Store

**[GEN-MANIFE-0005]** `SHALL`  
The C2PA Assertion Store is a superbox that shall have a label of c2pa.assertions and a JUMBF type UUID of 63326173-0011-0010-8000-00AA00389B71 (c2as).

**[GEN-MANIFE-0006]** `SHALL`  
It shall contain one or more JUMBF superboxes (called C2PA Assertion boxes) whose JUMBF type defines the BMFF type of the sub-boxes that contain the assertion data (ISO 19566-5:2023, Annex B).

**[GEN-MANIFE-0007]** `SHALL`  
These superboxes shall each have a label as defined in Standard Assertions.

**[GEN-MANIFE-0008]** `SHALL NOT`  
The C2PA Assertion Store shall not contain any JUMBF boxes or superboxes that are not JUMBF Content Boxes.

### 11.1.4.5. Ingredient Storage

**[GEN-MANIFE-0009]** `SHALL`  
When a C2PA Manifest includes ingredient assertions, and an ingredient contains a C2PA Manifest, that C2PA Manifest shall be included to ensure that the provenance data is kept intact.

### 11.2.2. Standard Manifests

**[GEN-MANIFE-0010]** `SHALL NOT`  
Manifest Consumers shall also accept standard C2PA Manifests specified with JUMBF type UUID 63326D64-0011-0010-8000-00AA00389B71 (c2md), but claim generators shall not create manifests with this JUMBF type UUID.

### 11.2.5. Time-Stamp Manifests

**[GEN-MANIFE-0011]** `SHALL`  
A Time-Stamp Manifest shall contain only a single assertion, which is the c2pa.ingredient.v3 assertion that (a) includes an activeManifest field with a value that is the URI reference to that C2PA Manifest that is being updated and (b) has the value of parentOf for the relationship field.


## Cryptography

*2 requirements*

### 13.2.4. Signature Validation

**[GEN-CRYPTO-0001]** `SHOULD`  
When producing a signature, if the claim generator can also act as a validator, the claim generator should validate that the signing credential is acceptable according to Chapter 14, Trust Model and produce a warning if it is not.

**[GEN-CRYPTO-0002]** `MAY`  
The claim generator may still allow signing with that credential if so desired.


## Trust Model

*7 requirements*

### 14.4.3. Private Credential Storage

**[GEN-TRUST_-0001]** `SHALL NOT`  
If present, the private credential store shall only apply to validating signed C2PA manifests, and shall not apply to validating time-stamps.

### 14.5. X.509 Certificates

**[GEN-TRUST_-0002]** `SHALL`  
Therefore, when creating the x5chain header as part of signing, the claim generator shall include the signer’s certificate and all intermediate certificate authorities in the header’s value.

**[GEN-TRUST_-0005]** `SHALL`  
Claim generators shall place this header only in the protected header bucket of the COSE signature as required above.

**[GEN-TRUST_-0003]** `SHOULD`  
Claim generators should use only the integer 33 as the label when inserting this header into a COSE signature.

**[GEN-TRUST_-0004]** `SHOULD`  
Claim generators may continue to write the string label x5chain but this behaviour is now deprecated and claim generators should be updated to use the integer label only.

### 14.5.2. Certificate Revocation

**[GEN-TRUST_-0007]** `SHALL NOT`  
The claim generator shall not use Certificate Revocation Lists (CRLs, see RFC 5280). ``

**[GEN-TRUST_-0006]** `SHOULD`  
A claim generator should use the Online Certificate Status Protocol (OCSP, see RFC 6960) and OCSP stapling (as originally conceptualized in RFC 6066, Section 8, but implemented as described in this clause) to implement revocation.


## Standard Assertions

*52 requirements*

### 18.12.2. Mandatory presence of at least one actions assertion

**[GEN-STANDA-0021]** `SHALL`  
There shall be at least one actions assertion in every standard C2PA Manifest:

**[GEN-STANDA-0022]** `SHALL`  
If the asset was created de novo (for example, as a result of performing a File → New operation in a creative tool, capturing a photo or video, or generating the media by a generative AI model), then the actions array in the c2pa.actions assertion shall begin with a c2pa.created action as its first element.

**[GEN-STANDA-0023]** `SHALL`  
If the asset is created with no digital content, then there shall be no digitalSourceType value in conjunction with the c2pa.created action.

**[GEN-STANDA-0024]** `SHALL`  
For all other assets, a corresponding digitalSourceType value shall be recorded with the c2pa.created action, to indicate the nature of the asset at its inception.

**[GEN-STANDA-0025]** `SHALL`  
If the asset was created by opening an existing asset as a parentOf ingredient for editing, then the actions array in the c2pa.actions assertion shall begin with an action of c2pa.opened as its first element.

**[GEN-STANDA-0026]** `SHALL`  
The mandatory c2pa.created or c2pa.opened action shall be recorded in the first instance of the c2pa.actions.v2 assertion, that is, the one that does not have an instance label.

**[GEN-STANDA-0027]** `SHALL`  
Additionally, the c2pa.actions.v2 assertion that does not have an instance label shall be placed earlier than any other actions assertion in the created_assertions array in c2pa.claim.v2.

### 18.12.3. Fields in the actions assertion

**[GEN-STANDA-0028]** `SHALL`  
If present, the reason field shall contain one of these standard values, or a custom value which conforms to the same syntax as entity-specific namespacing, for the rationale behind the action:

**[GEN-STANDA-0029]** `SHALL`  
When using a c2pa.redacted action, the reason field shall contain the rationale for the redaction.

**[GEN-STANDA-0030]** `SHALL`  
If included, the value of the when field shall be compliant with ISO 8601.

**[GEN-STANDA-0031]** `SHALL`  
When multiple softwareAgents are used, as described in Section 18.12.6.1.2, “SoftwareAgents”, then the softwareAgentIndex field shall be used to reference the softwareAgent by its 0-based index in the softwareAgents array.

**[GEN-STANDA-0032]** `SHALL`  
A given action shall only have one softwareAgent or softwareAgentIndex field.

**[GEN-STANDA-0033]** `SHALL`  
An action may include a digitalSourceType key, whose value shall be one of the terms defined by the IPTC or a C2PA specific value from the list below:

### 18.13.12. Determining the need to copy or copy and re-label existing manifests

**[GEN-STANDA-0037]** `SHALL`  
To determine whether or not an existing manifest from the ingredient’s C2PA Manifest Store needs to be copied into the asset’s C2PA Manifest Store, the claim generator shall:

**[GEN-STANDA-0040]** `SHALL`  
The claim generator shall check if any assertions from either manifest were redacted (optionally utilizing the list of redactions compiled in the Performing explicit validation process).

**[GEN-STANDA-0042]** `SHALL`  
If all redactions were applied against the manifest from the ingredient’s Manifest Store, then the claim generator shall replace the manifest in the asset’s C2PA Manifest Store with the manifest from the ingredient’s C2PA Manifest Store.

**[GEN-STANDA-0043]** `SHALL`  
If different redactions were applied against both the C2PA Manifest from the ingredient’s C2PA Manifest Store and the asset’s C2PA Manifest Store, then the claim generator shall redact as many assertions as needed from the existing manifest in the asset’s C2PA Manifest Store to result in a union of the two sets of redactions.

**[GEN-STANDA-0044]** `SHALL`  
In all other cases, then the claim generator shall copy the manifest from the ingredient’s C2PA Manifest Store, re-label it with an updated URN per the process described in Unique Identifiers, and insert the re-labeled version into the asset’s C2PA Manifest Store.

**[GEN-STANDA-0039]** `SHALL NOT`  
If the hashes match, then the claim generator shall not copy the manifest from the ingredient’s C2PA Manifest Store to the asset’s C2PA Manifest Store.

**[GEN-STANDA-0041]** `SHALL NOT`  
If all redactions were applied against the manifest already present in the asset’s C2PA Manifest Store, then the claim generator shall not copy the manifest from the ingredient’s C2PA Manifest Store into the asset’s C2PA Manifest Store.

**[GEN-STANDA-0038]** `MAY`  
In case of validation failures, the claim generator may skip the rest of these steps if directed to do so (for example, via user input or via configuration).

### 18.13.12.1.1. General

**[GEN-STANDA-0045]** `SHALL`  
In addition, when the ingredient assertion references a C2PA Manifest, the claim generator shall also act as a validator, performing validation of the ingredient as described in validation steps.

### 18.13.12.1.2. V2 ingredient assertions (DEPRECATED)

**[GEN-STANDA-0046]** `SHALL`  
The code shall conform to the same syntax as entity-specific namespaces (e.g. com.litware.malformedFrobber) and the validationStatus object shall contain a success boolean.

### 18.13.12.1.3. V3 ingredient assertions

**[GEN-STANDA-0048]** `SHALL`  
In a v3 ingredient assertion with an activeManifest field, the validationResults field shall contain a validation-results-map object which in turn contains:

**[GEN-STANDA-0049]** `SHALL`  
The delta validation results for an ingredient assertion shall contain the following:

**[GEN-STANDA-0050]** `SHALL`  
This status value comparison shall consider the status type (success, informational, or failure), code, and url, ignoring other fields.

**[GEN-STANDA-0051]** `SHALL`  
Each code is represented as a status-map object which shall contain a code field with the status code.

**[GEN-STANDA-0052]** `SHALL`  
The code shall conform to the same syntax as entity-specific namespaces (e.g. com.litware.malformedFrobber).

**[GEN-STANDA-0047]** `SHALL NOT`  
In a v3 ingredient assertion with no activeManifest field, the validationResults field shall not be present.

### 18.13.3. Relationship

**[GEN-STANDA-0034]** `SHALL`  
When adding an ingredient assertion, a claim generator shall add a c2pa.actions assertion (see Section 18.12, “Actions”), if one does not already exist in the active manifest.

### 18.13.5. Format

**[GEN-STANDA-0035]** `SHALL`  
It is recommended that a Claim Generator should provide this field and it shall contain a valid value.

### 18.13.8.1. Standard Usage

**[GEN-STANDA-0036]** `SHOULD`  
Claim generators should take the size of this field into consideration when choosing whether to embed data.

### 18.3.7.2. Localization Dictionary

**[GEN-STANDA-0001]** `SHOULD`  
In order for a Manifest Consumer to display human-readable information about these keys and values, the claim generator should provide the strings via this localization approach.

### 18.5.1. Description

**[GEN-STANDA-0002]** `SHALL NOT`  
Claim generators shall not add this field to a data hash assertion, and consumers shall ignore the field when present, except this shall not affect inclusion of the field as part of the content being validated as described in Section 15.10.3, “Assertion Validation”.

### 18.6.1. Description

**[GEN-STANDA-0003]** `SHALL NOT`  
Claim generators shall not add this field to a BMFF hash assertion, and consumers shall ignore the field when present, except this shall not affect inclusion of the field as part of the content being validated as described in Section 15.10.3, “Assertion Validation”.

### 18.7.1. Description

**[GEN-STANDA-0004]** `SHOULD`  
A claim generator should use a general box hash assertion to verify the integrity, with a hard binding (i.e., cryptographic hash), of assets whose formats use a non-BMFF-based box format such as JPEG, PNG, or GIF.

### 18.8.3. Fields

**[GEN-STANDA-0005]** `SHALL`  
A claim generator shall validate or sanitize the URIs before use, ensuring that neither . nor .. appear as part of the URI.

### 18.9.1. Description

**[GEN-STANDA-0006]** `SHALL NOT`  
Claim generators shall not add this field to a soft binding assertion, and consumers shall ignore the field when present, except this shall not affect inclusion of the field as part of the content being validated as described in Section 15.10.3, “Assertion Validation”.

**[GEN-STANDA-0007]** `SHALL NOT`  
Claim generators shall not add this field to a soft binding assertion, and consumers should ignore the field when present.

### 18.9.4. Soft Binding Algorithm List

**[GEN-STANDA-0008]** `SHALL`  
The alg field shall correspond to the alg field of an algorithm present in that list.

**[GEN-STANDA-0010]** `SHALL`  
The unique name of the algorithm is given in the alg field, and corresponds to the string that shall be used in the alg field a soft binding assertion that uses that algorithm.

**[GEN-STANDA-0011]** `SHALL`  
The name shall follow the namespacing requirements and represent the owner of the algorithm.

**[GEN-STANDA-0012]** `SHALL`  
If different versions of an algorithm are provided, then each shall have a separate entry in the Soft Binding Algorithm List.

**[GEN-STANDA-0013]** `SHALL`  
The type of the algorithm shall be either 'watermark' or 'fingerprint' to represent that the algorithm is an invisible watermark, or a fingerprint.

**[GEN-STANDA-0015]** `SHALL`  
The soft binding algorithm list entry shall contain a list of supported media types either as encodedMediaTypes or as decodedMediaTypes.

**[GEN-STANDA-0016]** `SHALL`  
The supported media types for decodedMediaTypes shall correspond to one more of the top-level IANA media types comprising of: "application", "audio", "image", "model", "text", "video".

**[GEN-STANDA-0017]** `SHALL`  
The supported media types for encodedMediaTypes shall correspond to one more of the registered IANA subtypes of a decodedMediaType listed in the preceding sentence.

**[GEN-STANDA-0018]** `SHALL`  
Additional information shall accompany each entry in the soft binding algorithm list, within the entryMetadata field.

**[GEN-STANDA-0019]** `SHALL`  
The contact details of the owner of the entry shall be provided as an email address (contact, required).

**[GEN-STANDA-0020]** `SHALL`  
An informational URL (informationalUrl, required) shall be provided that references a human readable page describing characteristics of the soft binding algorithm.

**[GEN-STANDA-0009]** `SHALL NOT`  
Entries in the soft binding algorithm list that have a deprecated field of true shall be considered deprecated and shall not be used to create soft binding assertions in manifests.

**[GEN-STANDA-0014]** `SHALL NOT`  
C2PA Manifests shall not be written using deprecated soft-bindings.
