# Attempt 1 budget abort

The registered launcher completed 171 of 172 responses. Before the final network request, `CallBudget.reserve` refused the exact registered boundary because binary floating-point accumulation produced `2114.418000000001` seconds against the `2114.418`-second cap.

The only missing registered cell is `e4dir-10465-5-t009-d0-global` (`10465-5-t009`, `D0-global`, 11.276 seconds). The refused request was not sent. No response text from the partial sink was read or scored. The owner explicitly authorized a one-cell technical supplement on 2026-08-21; all other model contact remains prohibited.
