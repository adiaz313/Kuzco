-- Fixed, inspectable Music adapter. User data arrives as argv, never script source.
on run argv
    set operation to item 1 of argv
    tell application "Music"
        if operation is "state" then
            if player state is playing then return "playing"
            if player state is paused then return "paused"
            return "stopped"
        else if operation is "track_id" then
            try
                return persistent ID of current track
            on error
                return "none"
            end try
        else if operation is "verify_playlist" then
            try
                if player state is playing and name of current playlist is item 2 of argv then return "playing"
            end try
            return "mismatch"
        else if operation is "verify_song" then
            try
                if player state is playing and name of current track is item 2 of argv then return "playing"
            end try
            return "mismatch"
        else if operation is "play" then
            if player state is stopped then
                -- Music has no current queue to resume; use its native library.
                play library playlist 1
            else
                play
            end if
        else if operation is "resume" then
            play
        else if operation is "pause" then
            if player state is stopped then return "no_active_media"
            pause
        else if operation is "next" then
            if player state is stopped then return "no_active_media"
            next track
        else if operation is "previous" then
            if player state is stopped then return "no_active_media"
            back track
        else if operation is "playlist" or operation is "song" or operation is "auto" then
            set wanted to item 2 of argv
            set foundItems to {}
            if operation is "playlist" or operation is "auto" then
                set foundItems to (every playlist whose name is wanted)
            end if
            if (count of foundItems) is 0 and (operation is "song" or operation is "auto") then
                set foundItems to (every track of library playlist 1 whose name is wanted)
            end if
            if (count of foundItems) is 0 then return "not_found"
            if (count of foundItems) > 1 then return "ambiguous"
            play item 1 of foundItems
        else
            return "unsupported"
        end if
        -- The play command can be asynchronous. Verification happens in a
        -- separate script invocation after this Apple event has returned.
        return "accepted"
    end tell
end run
