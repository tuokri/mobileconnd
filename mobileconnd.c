/**
 * \file mobileconnd.c
 * \brief Guess internet connection status by pinging google.com
 *        and call mobile connection dialing script if needed.
 */

#include <stdio.h>
#include <stdlib.h>
#include <signal.h>
#include <string.h>
#include <unistd.h>

volatile sig_atomic_t DONE = 0;
pid_t CHILD_PID = -1;

// TODO: Modularize?
const char* const DIALSCRIPT = "autowvdial";
const char* const MODEM      = "/dev/gsmmodem";
const char* const DIALER     = "LTE";
const char* const PIN        = "00000000";
const char* const TIMEOUT    = "60";

void terminate(int signo)
{
    if(signo == SIGTERM || signo == SIGINT)
    {
        DONE = 1;
        kill(CHILD_PID, SIGTERM);
    }
}

int main()
{
    puts("starting mobileconnd");

    struct sigaction action;
    memset(&action, 0, sizeof(struct sigaction));
    action.sa_handler = terminate;
    sigaction(SIGTERM, &action, NULL);
    sigaction(SIGINT, &action, NULL);

    while(!DONE)
    {
        int status = system("ping -c 1 -I ppp0 google.com > /dev/null");
        if(status != EXIT_SUCCESS)
        {
            puts("ping failed");

            // Ping failed but we already have a child.
            // Did the dialer script hang or error?
            // Kill the child and spawn a new one.
            if(CHILD_PID != -1)
            {
                puts("autowvdial already running, killing...");
                kill(CHILD_PID, SIGTERM);
                sleep(5); // Grace period.
                kill(CHILD_PID, SIGKILL);
                CHILD_PID = -1;
                puts("autowvdial killed");
            }

            if((CHILD_PID = fork()) < 0)
            {
                perror("fork error");
                exit(EXIT_FAILURE);
            }
            else if(CHILD_PID == 0)
            {
                puts("starting autowvdial");
                execlp(DIALSCRIPT, DIALSCRIPT, MODEM, PIN, "-d",
                    DIALER, "-t", TIMEOUT, (char*)NULL);
                perror("execlp error");
                _exit(EXIT_FAILURE);
            }
        }
        else
        {
            puts("ping succesful");
        }

        puts("sleeping for 5 minutes...");
        sleep(60 * 5);
    }

    printf("done, exiting");
    return 0;
}
