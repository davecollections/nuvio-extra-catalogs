# Published work mapping and artwork review

Reviewed 2026-09-26 for Issues #41 and #43, before V1.4 owner acceptance.

All 172 published catalogues were inventoried: **3,235 unique works** (2,306 movies and 929 series), covering Academy Awards, Golden Globes, BAFTA Film, BAFTA Television and BAFTA Television Craft. Every published item has canonical award provenance. The scan found no conflicting canonical TMDB IDs for one work, no IMDb ID published under both media types, and no mapped TMDB record linking a different IMDb ID.

The live pass checked each catalogue poster URL, each stored TMDB work ID and its external IDs, and TMDB’s IMDb lookup even where a poster already loaded. Missing-poster and IMDb-only records also received title searches (the first result page for up to two canonical title forms). This is a consistency and exception review of the existing source-backed mappings, not a new manual transcription of every historical award or a visual review of every poster. Full Nuvio detail-provider coverage remains recorded separately in the BAFTA metadata audits.

**3,084 works have an available image; 151 still have no verified available poster.** There were zero external-service failures in the completed scan. The 230 entries with flags have recorded dispositions tied to a hash of their evidence. One candidate identity ambiguity remains open, as described below.

## Changes

| Work | Correction |
| --- | --- |
| Glastonbury 2019 | Matching poster from TMDB TV 317120, season 23; keep IMDb tt10533670 as its separately identified annual event. |
| Glastonbury 2024 | Matching poster from TMDB TV 317120, season 28; keep IMDb tt36564052. Applied to Craft and Television. |
| King Gimp | Exact IMDb tt0239528 / TMDB movie 244949 poster, reused through the existing poster-contract validator. |
| A Simple Man | Add the verified TMDB movie 494464 relationship to IMDb tt0269866 and use its poster. |
| Leaving Home | Match the 1996 Simon Rattle series to TMDB 243767’s DVD edition; preserve IMDb tt0379127, original title and broadcast year, and use the matching poster. |
| Our Land | Correct the 2022 BAFTA winner to Alexandra Genova’s 2021 documentary (IMDb tt19268738), replacing the unrelated Swedish drama; retain a blank poster and add the exact compact metadata fallback. |
| Summer Comedy Shorts | Add verified TVDB promotional artwork linked to the exact existing IMDb series ID. |
| Notes on a Triangle; The Governor & J.J. | Their existing MetaHub URLs now return images. Remove stale unavailable-poster classifications; no URL change is needed. |

Catalogue IDs remain stable. The Our Land IMDb item changes from the unrelated Swedish drama tt13649306 to the verified documentary tt19268738; see the [correction and saved-item migration note](../docs/awards-corrections.md). The earlier preview separately corrected Festival of Remembrance and recovered Eurovision and Tea Party artwork.

## Coverage

Counts below are unique within each award body; a work can occur in more than one body.

| Award body | Published works | Image available | No verified image |
| --- | ---: | ---: | ---: |
| academy-awards | 1265 | 1261 | 4 |
| golden-globes | 1065 | 1065 | 0 |
| bafta-film | 821 | 801 | 20 |
| bafta-television | 665 | 575 | 90 |
| bafta-television-craft | 434 | 392 | 42 |

## Identity exceptions

- **Trouble in Tahiti:** the existing reviewed IMDb tt36896747 records the LWT/PBS production with a later 1976 date. TMDB movie 945191 describes the 1973 Bill Hays / Leonard Bernstein production but links IMDb tt14003470. The [Bernstein archive](https://leonardbernstein.com/news/blog/181/from-the-archives-trouble-in-tahiti) corroborates the 1973 production; the two IMDb records could not be independently reconciled. The current identity is retained and the candidate image is withheld. This remains an explicit uncertainty, not a claim that either record has been disproved.
- **Top Boy, Dahmer, Life and Death Row, Leaving Home:** TMDB maintains split or duplicate programme records. The reviewed production and stable IMDb identity are retained, with individual reasons in the JSON report. IMDb lookup results are not automatically substituted for a reviewed continuation, season or DVD-edition relationship.
- **Murder:** the 2012 pilot is explicitly present as special season 0 episode 1 of TMDB 65789; the 2016 main-series date does not invalidate the existing parent-series mapping for the 2013 award.
- **News at Ten:** IMDb retains the continuing programme from 1967, while TMDB dates its 2008 revival. Historical awards keep the original programme identity.
- **The Merry Widow:** TMDB’s detail response currently has corrupted title text, while its IMDb lookup, production date and credits identify the correct 1934 film. The canonical title is retained.
- **Earlier award / later release date:** Babe, Tango, Franz Kafka’s It’s a Wonderful Life, Baka, Falling Apart, Fish Never Sleep and Poor Little Rich Girl have later stored release dates than one or more award years. Their reviewed work identities are retained. These are recorded date discrepancies, not silently treated as a new production or comprehensively normalized in this artwork review.
- **Eight media/granularity differences:** TMDB’s IMDb lookup returns a parent series, episode, or event film where the reviewed catalogue uses a standalone movie or full event series. Each has an explicit disposition; no cross-media replacement is automatic.
- **126 works lack a stored TMDB relationship:** this is compatible with the catalogue-led design. Reviewed IMDb identities remain usable for installed metadata providers; absence of a TMDB ID is not itself a mapping error.

## Screenshot examples

Glastonbury 2019 and 2024 now have verified edition-specific artwork. Eurovision was repaired in the preceding preview. Death, Witness, Nice Girl, FA Cup Final 2014, World War One Remembered, Festival of Remembrance and John & Joe Bishop: Life After Deaf remain documented gaps. Similar names, another year’s event and the separate John Bishop companion production are not accepted as replacement images.

## Follow-up production check and owner preference

The owner requested blanks until real artwork is available; no generated title cards or substitute-film images are used. TVDB series [408509](https://thetvdb.com/series/summer-comedy-shorts) links the exact Summer Comedy Shorts IMDb ID. Its portrait promotional image was visually reviewed and returned HTTP 200 with image content. TVDB series [98491](https://thetvdb.com/series/true-stories) also links the correct True Stories IMDb ID, but its plain title graphic is withheld to respect the owner’s preference for real artwork.

Our Land demonstrates a limit of reciprocal IMDb/TMDB checks: both databases can agree on a production that was selected for the wrong award. The corrected identity is tied to [BAFTA’s credits](https://static.bafta.org/uploads_pre_202411/baftatv22winnerslist.pdf) and [the credited cinematographer’s production page](https://www.alfredthirolle.com/portfolio/our-land-1). The other named Short Form winners were checked against live TMDB production credits: Brain in Gear (Ikumelo/Costello/Gordon), They Saw the Sun First (Hunt/Gee), How to Be a Person (Agha), Mobility (Carroll/Meeda/Simpson/Ward), Quiet Life (Pickett/Rollason/Bruce), and Hustle and Run (Madderson/Stevens/Conlon). Missed Call matches [Victoria Mapplebeck’s film](https://victoriamapplebeck.com/films/missed-call/); Summer Comedy Shorts matches the exact IMDb-linked Sky Arts series. No further mismatch was found in this Short Form review. This does not certify every historical production credit across all awards.

The other latest screenshot gaps—Ellie Simmonds: Finding My Secret Family, How to Be a Person, Missed Call, True Stories, Only Human and One Life—still have no verified portrait poster through the reviewed routes. Editorial stills are not silently stretched into posters. The corrected Our Land joins the gap list. Nuvio returns an empty meta object for its correct IMDb ID; Cinemeta resolves it, and the reviewed compact fallback preserves that same ID.

## Sports screenshot follow-up

The two Sports Coverage film entries were unrelated fiction selected by title/year: The Ashes was Jacob Kirby’s Las Cenizas, and The Open was Marc Lahore’s fictional tennis film. [BAFTA’s archive](https://www.bafta.org/awards/television/sports-coverage/), [the 2016 Sky Sports credit list](https://static.bafta.org/uploads_pre_202411/baftatv1516nominationlist.pdf) and [Sky’s 2017 award announcement](https://www.skysports.com/golf/news/14866/10878191/sky-sports-coverage-of-the-open-wins-bafta-award) identify cricket and the 2016 Royal Troon golf broadcast instead.

The Ashes now uses the already published cricket event-series IMDb tt9090184 and deduplicates its 2006/2016 wins. The Open is preserved as an explicit non-catalogue result until a compatible live-broadcast IMDb identity is verified; the official-film compilation tt3889116 is not substituted. All 23 Sports Coverage identity decisions now have a reviewed override or explicit omission, and the identity validator rejects automatic title/year-only mappings for this category. Existing documented event/parent-series decisions remain in force; this does not assert a fresh independent re-verification of every historical episode credit.

All 16 remaining sports-series MetaHub routes were checked live: three images load and 13 return 404. Paris 2024 now has an additional verified TVDB fallback, leaving 12 blanks in this series row. Its portrait uses the Paris 2024 emblem and Olympic rings. TVDB 452671 was matched independently by event, dates and episode coverage; it does not link IMDb directly, and its obsolete TMDB link returns 404. No replacement TMDB identity was invented.

The released Sports Coverage Films catalogue ID and preset route remain available with an empty metas array. Existing installations keep their stable route; they no longer receive either unrelated film. The series route retains 16 unique sports titles, with The Ashes ordered by its latest win. Direct saves of the incorrect fiction IDs are not redirected. See the [correction and migration record](../docs/awards-corrections.md).

## Reproduction and limits

Use `scripts/audit_awards_work_mappings.py --cache <local-file> --workers 12` with the existing TMDB read-token environment variable. The optional checkpoint contains only public response evidence; it must be removed or omitted for a completely fresh pass. Changed catalogue inventory is rechecked automatically. Review changed flags before `--offline-check`; that gate rejects incomplete inventory, service errors, stale evidence or missing flag dispositions. The live report is [`awards-work-mapping-audit.json`](awards-work-mapping-audit.json).

Catalogue previews supply poster URLs along with IDs. Full metadata is a separate request to a compatible installed provider. A blank image can therefore coexist with a correct ID and working title details. This pass does not add a backend, new metadata-provider scope, people artwork or Emmy implementation. V1.4 remains a draft preview requiring owner acceptance in Nuvio.

## Remaining poster gaps

These are unavailable through the reviewed routes at the check time; the list is not a claim that no image exists anywhere.

| IMDb ID | Type | Catalogue title | Award bodies |
| --- | --- | --- | --- |
| [tt0058410](https://www.imdb.com/title/tt0058410/) | movie | Nine from Little Rock | academy-awards |
| [tt0062184](https://www.imdb.com/title/tt0062184/) | movie | The Redwoods | academy-awards |
| [tt0064847](https://www.imdb.com/title/tt0064847/) | movie | Prologue | bafta-film |
| [tt0066261](https://www.imdb.com/title/tt0066261/) | movie | Put Out More Flags | bafta-television-craft |
| [tt0067875](https://www.imdb.com/title/tt0067875/) | movie | Traitor | bafta-television |
| [tt0069020](https://www.imdb.com/title/tt0069020/) | movie | Norman Rockwell's World...An American Dream | academy-awards |
| [tt0086354](https://www.imdb.com/title/tt0086354/) | movie | Stan's Last Game | bafta-television-craft |
| [tt0087725](https://www.imdb.com/title/tt0087725/) | movie | Sagan om livet | bafta-television |
| [tt0092583](https://www.imdb.com/title/tt0092583/) | movie | The Artist | bafta-film |
| [tt0110800](https://www.imdb.com/title/tt0110800/) | movie | Pauline Calf's Wedding Video | bafta-television |
| [tt0145743](https://www.imdb.com/title/tt0145743/) | movie | Do Be Careful Boys | bafta-film |
| [tt0162925](https://www.imdb.com/title/tt0162925/) | movie | The Deadness of Dad | bafta-film |
| [tt0204589](https://www.imdb.com/title/tt0204589/) | movie | Rembrandt | bafta-television-craft |
| [tt0206000](https://www.imdb.com/title/tt0206000/) | movie | The Harmfulness of Tobacco | bafta-film |
| [tt0212512](https://www.imdb.com/title/tt0212512/) | movie | The South African Experience: Six Days of Soweto | bafta-television |
| [tt0215490](https://www.imdb.com/title/tt0215490/) | movie | Alaska: The Great Land | bafta-film |
| [tt0215587](https://www.imdb.com/title/tt0215587/) | movie | Butch Minds the Baby | bafta-film |
| [tt0215591](https://www.imdb.com/title/tt0215591/) | movie | The Candy Show | bafta-film |
| [tt0215736](https://www.imdb.com/title/tt0215736/) | movie | The Early Americans | bafta-film |
| [tt0217625](https://www.imdb.com/title/tt0217625/) | movie | Lockerbie: A Night Remembered | bafta-television-craft |
| [tt0246812](https://www.imdb.com/title/tt0246812/) | movie | Nice Girl | bafta-television-craft |
| [tt0247500](https://www.imdb.com/title/tt0247500/) | movie | The Man with the Beautiful Eyes | bafta-film |
| [tt0248793](https://www.imdb.com/title/tt0248793/) | movie | Facing the Music: The Return of Torvill and Dean | bafta-television-craft |
| [tt0275669](https://www.imdb.com/title/tt0275669/) | movie | Shadowscan | bafta-film |
| [tt0296863](https://www.imdb.com/title/tt0296863/) | movie | The Stanley Baxter Big Picture Show | bafta-television, bafta-television-craft |
| [tt0296864](https://www.imdb.com/title/tt0296864/) | movie | The Stanley Baxter Moving Picture Show | bafta-television |
| [tt0305390](https://www.imdb.com/title/tt0305390/) | movie | Coping with Christmas | bafta-television |
| [tt0340071](https://www.imdb.com/title/tt0340071/) | movie | This Charming Man (Der Er En Yndig Mand) | academy-awards |
| [tt0350920](https://www.imdb.com/title/tt0350920/) | movie | Feltham Sings | bafta-television |
| [tt0360861](https://www.imdb.com/title/tt0360861/) | movie | Pan-tele-tron | bafta-film |
| [tt0396515](https://www.imdb.com/title/tt0396515/) | movie | Brown Paper Bag | bafta-film |
| [tt0415181](https://www.imdb.com/title/tt0415181/) | movie | Nine Lives of Alice Martineau | bafta-television-craft |
| [tt0443534](https://www.imdb.com/title/tt0443534/) | movie | Holocaust: A Music Memorial Film | bafta-television |
| [tt0490208](https://www.imdb.com/title/tt0490208/) | movie | SAS: Iranian Embassy Siege | bafta-television-craft |
| [tt0595280](https://www.imdb.com/title/tt0595280/) | movie | Crown Matrimonial | bafta-television |
| [tt0793531](https://www.imdb.com/title/tt0793531/) | movie | Indus Waters | bafta-film |
| [tt0793570](https://www.imdb.com/title/tt0793570/) | movie | Rig Move | bafta-film |
| [tt0914794](https://www.imdb.com/title/tt0914794/) | movie | An Audience with Take That | bafta-television-craft |
| [tt1032863](https://www.imdb.com/title/tt1032863/) | movie | Do Not Erase | bafta-film |
| [tt10449278](https://www.imdb.com/title/tt10449278/) | movie | FA Cup Final 2014: Hull City FC vs. Arsenal FC | bafta-television-craft |
| [tt1059223](https://www.imdb.com/title/tt1059223/) | movie | La ronde | bafta-television-craft |
| [tt1152392](https://www.imdb.com/title/tt1152392/) | movie | Tsunami: 7 Hours on Boxing Day | bafta-television-craft |
| [tt1236238](https://www.imdb.com/title/tt1236238/) | movie | War Oratorio | bafta-television-craft |
| [tt1289398](https://www.imdb.com/title/tt1289398/) | movie | The Fallen | bafta-television-craft |
| [tt1517092](https://www.imdb.com/title/tt1517092/) | movie | I Do Air | bafta-film |
| [tt19268738](https://www.imdb.com/title/tt19268738/) | movie | Our Land | bafta-television |
| [tt1943839](https://www.imdb.com/title/tt1943839/) | movie | The Making Of Longbird | bafta-film |
| [tt2004332](https://www.imdb.com/title/tt2004332/) | movie | Random | bafta-television |
| [tt20447178](https://www.imdb.com/title/tt20447178/) | movie | Coping with Grown Ups | bafta-television |
| [tt2058136](https://www.imdb.com/title/tt2058136/) | movie | Wounded | bafta-television |
| [tt2205661](https://www.imdb.com/title/tt2205661/) | movie | The Secret Policeman | bafta-television |
| [tt2266799](https://www.imdb.com/title/tt2266799/) | movie | The Orphans of Nkandla | bafta-television |
| [tt22746690](https://www.imdb.com/title/tt22746690/) | movie | John & Joe Bishop: Life After Deaf | bafta-television-craft |
| [tt22987508](https://www.imdb.com/title/tt22987508/) | movie | Friday Night Live | bafta-television |
| [tt26660803](https://www.imdb.com/title/tt26660803/) | movie | BBC Beijing Olympics: Monkey, Journey to the West | bafta-television-craft |
| [tt2780146](https://www.imdb.com/title/tt2780146/) | movie | The Ball | bafta-film |
| [tt29538590](https://www.imdb.com/title/tt29538590/) | movie | The Queen's 90th Birthday Celebration | bafta-television |
| [tt3053868](https://www.imdb.com/title/tt3053868/) | movie | The Plot to Bring Down Britain's Planes | bafta-television-craft |
| [tt31846918](https://www.imdb.com/title/tt31846918/) | movie | Ellie Simmonds: Finding My Secret Family | bafta-television |
| [tt32189654](https://www.imdb.com/title/tt32189654/) | movie | Girls Wanted, Istanbul | bafta-television |
| [tt36896747](https://www.imdb.com/title/tt36896747/) | movie | Trouble in Tahiti | bafta-television-craft |
| [tt3704078](https://www.imdb.com/title/tt3704078/) | movie | Messiah at the Foundling Hospital | bafta-television-craft |
| [tt39074249](https://www.imdb.com/title/tt39074249/) | movie | Sky News: Hong Kong Protests | bafta-television |
| [tt4326224](https://www.imdb.com/title/tt4326224/) | movie | After Lockerbie | bafta-television |
| [tt4459770](https://www.imdb.com/title/tt4459770/) | movie | Don't Take My Baby | bafta-television |
| [tt7909898](https://www.imdb.com/title/tt7909898/) | movie | BBC Winter Olympics: The Fearless Are Here | bafta-television-craft |
| [tt8218408](https://www.imdb.com/title/tt8218408/) | movie | Missed Call | bafta-television |
| [tt0057734](https://www.imdb.com/title/tt0057734/) | series | The Big Noise | bafta-television |
| [tt0058856](https://www.imdb.com/title/tt0058856/) | series | The World of Wooster | bafta-television |
| [tt0075570](https://www.imdb.com/title/tt0075570/) | series | Rock Follies of '77 | bafta-television-craft |
| [tt0078653](https://www.imdb.com/title/tt0078653/) | series | Matilda's England | bafta-television-craft |
| [tt0081958](https://www.imdb.com/title/tt0081958/) | series | We, the Accused | bafta-television-craft |
| [tt0083384](https://www.imdb.com/title/tt0083384/) | series | The Bell | bafta-television-craft |
| [tt0092324](https://www.imdb.com/title/tt0092324/) | series | Blackadder the Third | bafta-television |
| [tt0094435](https://www.imdb.com/title/tt0094435/) | series | Christabel | bafta-television-craft |
| [tt0108748](https://www.imdb.com/title/tt0108748/) | series | Don't Forget Your Toothbrush | bafta-television |
| [tt0159228](https://www.imdb.com/title/tt0159228/) | series | Your Mother Wouldn't Like It | bafta-television |
| [tt0159852](https://www.imdb.com/title/tt0159852/) | series | Boyd Q.C. | bafta-television |
| [tt0179586](https://www.imdb.com/title/tt0179586/) | series | The Lively Arts | bafta-television-craft |
| [tt0211948](https://www.imdb.com/title/tt0211948/) | series | The Big Impression | bafta-television |
| [tt0229912](https://www.imdb.com/title/tt0229912/) | series | ITV News at Ten / News at Ten | bafta-television |
| [tt0264999](https://www.imdb.com/title/tt0264999/) | series | Sportsview | bafta-television |
| [tt0267154](https://www.imdb.com/title/tt0267154/) | series | Bookmark | bafta-television |
| [tt0283171](https://www.imdb.com/title/tt0283171/) | series | Back to the Floor | bafta-television |
| [tt0294156](https://www.imdb.com/title/tt0294156/) | series | Not So Much a Programme, More a Way of Life | bafta-television |
| [tt0294205](https://www.imdb.com/title/tt0294205/) | series | This Week | bafta-television |
| [tt0295815](https://www.imdb.com/title/tt0295815/) | series | Rory Bremner...Who Else? | bafta-television |
| [tt0296446](https://www.imdb.com/title/tt0296446/) | series | True Stories | bafta-television, bafta-television-craft |
| [tt0297595](https://www.imdb.com/title/tt0297595/) | series | Naked Hollywood | bafta-television |
| [tt0309129](https://www.imdb.com/title/tt0309129/) | series | Armchair Mystery Theatre | bafta-television |
| [tt0324697](https://www.imdb.com/title/tt0324697/) | series | Bluebell | bafta-television-craft |
| [tt0357396](https://www.imdb.com/title/tt0357396/) | series | Sky News: Live at Five | bafta-television |
| [tt0367292](https://www.imdb.com/title/tt0367292/) | series | Blackmail | bafta-television |
| [tt0367296](https://www.imdb.com/title/tt0367296/) | series | The Book Tower | bafta-television |
| [tt0388616](https://www.imdb.com/title/tt0388616/) | series | The Long Johns | bafta-television |
| [tt0397203](https://www.imdb.com/title/tt0397203/) | series | Sydney 2000: Games of the XXVII Olympiad | bafta-television |
| [tt0405611](https://www.imdb.com/title/tt0405611/) | series | The Wednesday Thriller | bafta-television |
| [tt0465319](https://www.imdb.com/title/tt0465319/) | series | Between the Wars | bafta-television-craft |
| [tt0479832](https://www.imdb.com/title/tt0479832/) | series | Granada Reports | bafta-television |
| [tt0480065](https://www.imdb.com/title/tt0480065/) | series | On the Move | bafta-television |
| [tt0499367](https://www.imdb.com/title/tt0499367/) | series | The Rise and Fall of César Birotteau | bafta-television |
| [tt0834479](https://www.imdb.com/title/tt0834479/) | series | The House | bafta-television |
| [tt0835702](https://www.imdb.com/title/tt0835702/) | series | Only Human | bafta-television |
| [tt0913749](https://www.imdb.com/title/tt0913749/) | series | Meeting Point | bafta-television |
| [tt0958966](https://www.imdb.com/title/tt0958966/) | series | W. Somerset Maugham | bafta-television |
| [tt0970163](https://www.imdb.com/title/tt0970163/) | series | Witness | bafta-television-craft |
| [tt0990517](https://www.imdb.com/title/tt0990517/) | series | The Ark | bafta-television |
| [tt10069230](https://www.imdb.com/title/tt10069230/) | series | Royal British Legion Festival of Remembrance | bafta-television, bafta-television-craft |
| [tt1015629](https://www.imdb.com/title/tt1015629/) | series | Death | bafta-television-craft |
| [tt10998480](https://www.imdb.com/title/tt10998480/) | series | ITV Sport: Rugby World Cup 2019 | bafta-television |
| [tt11608566](https://www.imdb.com/title/tt11608566/) | series | FYI - SKY News for Kids | bafta-television |
| [tt12740018](https://www.imdb.com/title/tt12740018/) | series | UEFA Women's Euro 2022 | bafta-television |
| [tt1330949](https://www.imdb.com/title/tt1330949/) | series | Thursday Theatre | bafta-television-craft |
| [tt1342999](https://www.imdb.com/title/tt1342999/) | series | Biography | bafta-television-craft |
| [tt1346933](https://www.imdb.com/title/tt1346933/) | series | The Root of All Evil? | bafta-television |
| [tt1351662](https://www.imdb.com/title/tt1351662/) | series | The Ritz | bafta-television |
| [tt13801796](https://www.imdb.com/title/tt13801796/) | series | Ipso Facto | bafta-television |
| [tt13839292](https://www.imdb.com/title/tt13839292/) | series | Now & Then | bafta-television |
| [tt1384817](https://www.imdb.com/title/tt1384817/) | series | Story Parade | bafta-television |
| [tt1461349](https://www.imdb.com/title/tt1461349/) | series | Sky World News | bafta-television |
| [tt1498696](https://www.imdb.com/title/tt1498696/) | series | 12th IAAF World Championships in Athletics Berlin 2009 | bafta-television |
| [tt15194044](https://www.imdb.com/title/tt15194044/) | series | Manchester 2002: XVII Commonwealth Games | bafta-television |
| [tt1540109](https://www.imdb.com/title/tt1540109/) | series | Formula 1: BBC Sport | bafta-television |
| [tt1553769](https://www.imdb.com/title/tt1553769/) | series | The Force | bafta-television-craft |
| [tt1586201](https://www.imdb.com/title/tt1586201/) | series | The System | bafta-television-craft |
| [tt1646040](https://www.imdb.com/title/tt1646040/) | series | Famous Gossips | bafta-television |
| [tt1817823](https://www.imdb.com/title/tt1817823/) | series | Blue Peter Special Assignment | bafta-television |
| [tt1887593](https://www.imdb.com/title/tt1887593/) | series | Welcome to Lagos | bafta-television |
| [tt20124924](https://www.imdb.com/title/tt20124924/) | series | How to Be a Person | bafta-television |
| [tt2295859](https://www.imdb.com/title/tt2295859/) | series | One Life | bafta-television |
| [tt28500169](https://www.imdb.com/title/tt28500169/) | series | River Journeys | bafta-television |
| [tt3013722](https://www.imdb.com/title/tt3013722/) | series | Police | bafta-television |
| [tt31848311](https://www.imdb.com/title/tt31848311/) | series | ITV Racing | bafta-television |
| [tt32085850](https://www.imdb.com/title/tt32085850/) | series | Middle English | bafta-television |
| [tt37740869](https://www.imdb.com/title/tt37740869/) | series | Match of the Day Live: Women's UEFA Euro 2025 | bafta-television, bafta-television-craft |
| [tt39045767](https://www.imdb.com/title/tt39045767/) | series | In Need of Special Care | bafta-film |
| [tt43277628](https://www.imdb.com/title/tt43277628/) | series | A Year in the Life | bafta-television |
| [tt43710601](https://www.imdb.com/title/tt43710601/) | series | Timmy and Vicki | bafta-television |
| [tt4489940](https://www.imdb.com/title/tt4489940/) | series | Cottage to Let | bafta-television |
| [tt5448310](https://www.imdb.com/title/tt5448310/) | series | Channel 4 Racing | bafta-television |
| [tt5643468](https://www.imdb.com/title/tt5643468/) | series | Blues and Twos | bafta-television-craft |
| [tt5763260](https://www.imdb.com/title/tt5763260/) | series | Formula 1: Sky Sports F1 | bafta-television |
| [tt6282482](https://www.imdb.com/title/tt6282482/) | series | First Tuesday | bafta-television |
| [tt6433734](https://www.imdb.com/title/tt6433734/) | series | The Grand National | bafta-television |
| [tt6556570](https://www.imdb.com/title/tt6556570/) | series | ITN News | bafta-television |
| [tt7205604](https://www.imdb.com/title/tt7205604/) | series | World War One Remembered | bafta-television, bafta-television-craft |
| [tt8023892](https://www.imdb.com/title/tt8023892/) | series | BBC Sport: Winter Olympics | bafta-television-craft |
| [tt8039182](https://www.imdb.com/title/tt8039182/) | series | The Duty Men | bafta-television |
| [tt9020296](https://www.imdb.com/title/tt9020296/) | series | Operatunity | bafta-television-craft |
| [tt9090184](https://www.imdb.com/title/tt9090184/) | series | The Ashes | bafta-television |
| [tt9406728](https://www.imdb.com/title/tt9406728/) | series | Wisden Trophy | bafta-television |
