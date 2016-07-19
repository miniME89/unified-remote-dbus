local timer = libs.timer
local server = libs.server
local data = libs.data
local json = nil

local properties = nil
local remotePositionChange = false
local remotePosition = 0
local remoteVolumeChange = false
local remoteVolume = 0
local lastVolume = 0
local fdmp, fdin, fdout, fderr = nil
local fdoutIterator = nil
local tid = -1

script_path = function()
   local str = debug.getinfo(2, "S").source:sub(2)
   return str:match("(.*/)")
end

exec = function(cmd, ...)
    fdin:write(cmd .. "\n")
    fdin:flush()

    local res = fdoutIterator()
    while res == nil do
        os.sleep(100)
        res = fdoutIterator()
    end

    return json:decode(res)
end

update = function()
    local connected = exec("isConnected")
    properties = exec("getProperties")

    -- metadata
    local title = ""
    local length = 0
    local metadata = properties["Metadata"]
    if not (metadata == nil) then
        -- title
        title = metadata["xesam:title"]
        if title == nil then title = "" end

        -- length
        length = metadata["mpris:length"]
        if length == nil then length = 0 end
    end

    -- status
    local status = properties["PlaybackStatus"]
    if status == nil then status = "Stopped" end

    -- position
    local position = properties["Position"]
    if remotePositionChange then position = remotePosition * 1000000 end
    if position == nil then position = 0 end

    -- volume
    local volume = properties["Volume"]
    if remoteVolumeChange then volume = remoteVolume / 100 end
    if volume == nil then volume = 0 end

    -- play/pause icon
    local playIcon = "playpause"
    if status == "Playing" then
        playIcon = "pause"
    elseif status == "Paused" then
        playIcon = "play"
    elseif status == "Stopped" then
        playIcon = "play"
    end

    -- mute icon
    local muteIcon = "vup"
    if volume == 0 then
        muteIcon = "vmute"
    elseif volume < 0.5 then
        muteIcon = "vdown"
    end

    -- not connected
    if not connected then
        title = "No player available"
    end

    -- adjust unit
    local lengthSec = math.floor(length / 1000000)     -- seconds
    local positionSec = math.floor(position / 1000000) -- seconds
    local volumePer = math.floor(volume * 100)         -- percent

    server.update(
        { id = "title", text = title },
        { id = "pos", progress = positionSec, progressmax = lengthSec, text = data.sec2span(positionSec) .. " / " .. data.sec2span(lengthSec) },
        { id = "vol", progress = volumePer, progressmax = 100},
        { id = "mute", icon = muteIcon },
        { id = "play", icon = playIcon }
    )
end

events.focus = function()
    json = loadfile(script_path() .. "JSON.lua")()

    -- popen cant open a read and write pipe (seriously?!)
    -- workaround: http://lua-users.org/lists/lua-l/2014-02/msg00540.html
    local tmpin, tmpout, tmperr = os.tmpname(), os.tmpname(), os.tmpname()
    fdin, fdout, fderr = io.open(tmpin, "w"), io.open(tmpout), io.open(tmperr)
    cmd = "python \"" .. script_path() .. "mediaplayer.py\" < " .. tmpin .. " > " .. tmpout .. " 2> " .. tmperr
    fdmp = assert(io.popen(cmd))
    fdoutIterator = fdout:lines()

    tid = timer.interval(update, 500)
    update()
end

events.blur = function()
    exec("quit")
    timer.cancel(tid)
    fdin:close()
    fdout:close()
    fderr:close()
    fdmp:close()
end

--@help Seek -30s
actions.seek_m_30 = function()
    exec("Seek," .. -30000000)
end

--@help Seek -5s
actions.seek_m_5 = function()
    exec("Seek," .. -5000000)
end

--@help Seek +5s
actions.seek_p_5 = function()
    exec("Seek," .. 5000000)
end

--@help Seek +30s
actions.seek_p_30 = function()
    exec("Seek," .. 30000000)
end

--@help Toggle play/pause
actions.play_pause = function()
    exec("PlayPause")
end

--@help Start playback
actions.play = function()
    exec("Play")
end

--@help Pause playback
actions.pause = function()
    exec("Pause")
end

--@help Stop playback
actions.stop = function()
    exec("Stop")
end

--@help Play next item
actions.next = function()
    exec("Next")
end

--@help Play previous item
actions.previous = function()
    exec("Previous")
end

--@help Change position
--@param vol:number Set Position
actions.position_change = function(pos)
    remotePositionChange = true
    remotePosition = pos
end

--@help Apply position
actions.position_apply = function()
    -- get track id
    local currentTrackid = ""
    if not (properties == nil) then
        local metadata = properties["Metadata"]
        if not (metadata == nil) then
            currentTrackid = metadata["mpris:trackid"]
            if currentTrackid == nil then currentTrackid = "" end
        end
    end

    exec("SetPosition,\"" .. currentTrackid .. "\"," .. (remotePosition * 1000000))

    timer.timeout(function ()
        remotePositionChange = false
    end, 500)
end

--@help Change volume
--@param vol:number Set Volume
actions.volume_change = function(vol)
    remoteVolumeChange = true
    remoteVolume = vol
end

--@help Apply volume
actions.volume_apply = function ()
    exec("setProperty,\"Volume\",float(" .. (remoteVolume / 100) .. ")")

    timer.timeout(function ()
        remoteVolumeChange = false
    end, 500)
end

--@help Toggle mute
actions.toggle_mute = function()
    local volume = properties["Volume"]
    if not (volume == nil) then
        if volume == 0 then
            exec("setProperty,\"Volume\",float(" .. lastVolume .. ")")
        else
            lastVolume = volume
            exec("setProperty,\"Volume\",float(0)")
        end
    end
end
