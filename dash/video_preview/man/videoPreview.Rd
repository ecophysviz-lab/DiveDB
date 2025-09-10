% Auto-generated: do not edit by hand
\name{videoPreview}

\alias{videoPreview}

\title{VideoPreview component}

\description{

}

\usage{
videoPreview(id=NULL, currentTime=NULL, endTime=NULL, isPlaying=NULL,
playheadTime=NULL, restrictedTimeRange=NULL,
selectedVideoId=NULL, startTime=NULL, style=NULL,
videoOptions=NULL, videoSrc=NULL)
}

\arguments{
\item{id}{Character. }

\item{currentTime}{Numeric. }

\item{endTime}{Numeric. }

\item{isPlaying}{Logical. }

\item{playheadTime}{Numeric. }

\item{restrictedTimeRange}{Lists containing elements 'start', 'end', 'starttimestamp', 'endtimestamp'.
those elements have the following types:
  - start (character; optional)
  - end (character; optional)
  - starttimestamp (numeric; optional)
  - endtimestamp (numeric; optional). Time range restrictions for video playback synchronization.}

\item{selectedVideoId}{Character. The ID of the currently selected video.}

\item{startTime}{Numeric. }

\item{style}{Named list. }

\item{videoOptions}{List of lists containing elements 'id', 'filename', 'filecreatedat', 'shareurl', 'originalurl', 'thumbnailurl', 'metadata'.
those elements have the following types:
  - id (character; required)
  - filename (character; required)
  - filecreatedat (character; required)
  - shareurl (character; optional)
  - originalurl (character; optional)
  - thumbnailurl (character; optional)
  - metadata (optional): . metadata has the following type: lists containing elements 'duration', 'originalfilename', 'type'.
those elements have the following types:
  - duration (character; optional)
  - originalfilename (character; optional)
  - type (character; optional)s. Array of available video options with metadata.}

\item{videoSrc}{Character. }
}

\value{named list of JSON elements corresponding to React.js properties and their values}

